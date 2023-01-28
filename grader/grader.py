import sys
import pathlib
import subprocess
import multiprocessing
import warnings

import pandas as pd
import numpy as np
from tqdm import tqdm
from timeit import default_timer as timer


from grader.student_code import StudentCode
from grader.solution_code import SolutionCode
from grader.test_cases import TestCaseGenerator
from grader.utils import Colors
from grader.code_parser import parse_py_file


class Grader:
    def __init__(self, args):
        self.solution_file = args.solution_file
        self.student_dir = args.student_dir
        self.max_grade = args.max_grade
        self.students = args.students
        self.multiprocessing_cores = args.multiprocessing

        # This is where the summary excel file will be saved
        self.summary_path = pathlib.Path(self.student_dir / f'{self.solution_file.stem}_summary.xlsx')

        # Add directories to the path so we can import the modules more easily later
        # and for the student's code to find files with open() as well
        sys.path.append(str(self.student_dir.resolve()))
        sys.path.append(str(self.solution_file.parent.resolve()))

        # Create directory to store feedback files
        self.feedback_dir = self.student_dir / 'feedback'
        if not self.feedback_dir.exists():
            self.feedback_dir.mkdir()

        # Directory to store original jupyter notebooks (if any)
        self.notebook_dir = self.student_dir / 'jupyter_notebooks'

        # Override libraries and then import solution
        self.override_libraries()
        self.sol_code = SolutionCode(self.solution_file)

    def override_libraries(self):
        """
        Override some library functions that we don't want to run in the grader.

        For example, we usually don't want to run calls to draw() functions in matplotlib.
        You can also use this to provide a fake/dummy module that the student code will use,
            a good example of such a case is to provide a google.colab module locally.
        """
        import matplotlib.pyplot
        import grader.empty_module

        matplotlib.pyplot.show = lambda: None
        sys.modules['matplotlib.pyplot'].show = lambda: None
        sys.modules['google.colab'] = grader.empty_module

    def convert_all_student_jupyter_to_py(self):
        """Converts all student Jupyter notebooks into regular Python script files."""
        all_jupyter_fpaths = list(self.student_dir.glob("*.ipynb"))
        if len(all_jupyter_fpaths) == 0:
            return

        # Create a directory to place the notebooks after conversion
        if not self.notebook_dir.exists():
            self.notebook_dir.mkdir()

        print(f'[Debug] Converting {len(all_jupyter_fpaths)} Jupyter notebooks')
        start_time = timer()
        if self.multiprocessing_cores <= 1:
            for fpath in tqdm(all_jupyter_fpaths):
                self.convert_one_student_jupyter_to_py(fpath)
        else:
            with multiprocessing.Pool(self.multiprocessing_cores) as pool:
                pool.map(self.convert_one_student_jupyter_to_py, all_jupyter_fpaths)
        print(f'[Debug] Converting Jupyter notebooks took {timer()-start_time:.2f}sec')

    def convert_one_student_jupyter_to_py(self, fpath):
        """Converts a given notebook into a Python script if needed."""
        # If the file has already been converted skip it (don't convert it again!)
        if fpath.with_suffix(".py").exists():
            fpath.rename(self.notebook_dir / fpath.name)
            return

        print(f"[Auto-Grader] Converting jupyter notebook {fpath.stem} into regular code")
        subprocess.call(['jupyter', 'nbconvert', '--to', 'python', str(fpath)])
        fpath.rename(self.notebook_dir / fpath.name)

    def grade_all_students(self):
        """Grades all students in the given student directory"""
        # Find all the student code files
        stu_files = list(self.student_dir.glob("*.py"))

        # If the --student parameter is passed in the command-line, grade only those students
        if self.students:
            temp_student_files = []
            for student_name in self.students:
                # Look for all Blackboard attempts
                attempts = []
                for att_path in stu_files:
                    att_path_split = att_path.stem.split('_')
                    if len(att_path_split) >= 4 and att_path_split[1] == student_name:
                        attempts.append(att_path)

                # If we find Blackboard attempts, grade those
                # If not, try to open the parameter as a file with
                if len(attempts) > 0:
                    temp_student_files.extend(sorted(attempts))
                else:
                    path = pathlib.Path(student_name)
                    assert path.exists(), f'Could not find {student_name} blackboard attempts or as a file'
                    temp_student_files.append(path)

            stu_files = temp_student_files

        self.all_student_files = set(stu_files)
        discard = set(['bst', 'btree', 'graph', 'dsf', 'min_heap'])
        for fpath in list(self.all_student_files):
            if fpath.stem in discard:
                self.all_student_files.discard(fpath)

        # Grade all students, suppressing their code warnings for cleaner output
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            all_scores = []
            if self.multiprocessing_cores <= 1:
                for fpath in self.all_student_files:
                    print('[Debug] Grading', fpath)
                    stu_scores = self.grade_one_student(fpath)
                    all_scores.append(stu_scores)
            else:
                with multiprocessing.Pool(self.multiprocessing_cores) as pool:
                    all_scores = pool.map(self.grade_one_student, self.all_student_files)

        # Create summary file
        self.df = pd.DataFrame.from_records(all_scores)
        print("Creating summary file with scores per problem")
        print(self.df)
        self.df.to_excel(self.summary_path, index=False)

    def grade_one_student(self, fpath: pathlib.Path):
        """Grades all functions of a given student."""

        with StudentCode(self.student_dir, fpath, self.all_student_files) as stu_code:
            # First we want to clean the code
            parse_py_file(stu_code)

            # Open a progress bar for visualization in the command-line
            stu_code.log(f'Importing module')
            stu_code.p_bar.total = 100

            # We will keep track of all problem grades in this dictionary
            scores = {fn_name: 0 for fn_name in self.sol_code.all_fnames}
            scores['student'] = stu_code.student_name
            scores['final_grade'] = 0

            # We will keep track of the total score from all problems in this int
            total_score = 0

            # Try to import the student's code
            import_exception = stu_code.import_module()
            scores['import_exception'] = import_exception
            if import_exception:
                stu_code.log(f'{Colors.T_MAGENTA}Import exception [{import_exception}]{Colors.T_RESET}')
                return scores

            # Go through all functions in the solution
            for idx, (fn_name, _) in enumerate(self.sol_code):
                # stu_code.p_bar.update()
                stu_code.log(f'Grading [{idx+1}/{len(self.sol_code)}], fn="{fn_name}"')
                stu_code.write_feedback(f'******************** [AutoGrader] Grading fn="{fn_name}" ********************')

                # Check if the student actually has the function
                if not stu_code.has_fn(fn_name):
                    stu_code.write_feedback(f'Did not find {fn_name} in the student code, assigning a grade of 0 to this problem')
                    scores[fn_name] = 0
                    continue

                # Grade the function
                scores[fn_name] = self.grade_one_function(fn_name, stu_code)
                total_score += scores[fn_name]

            # Summarize scores
            stu_code.write_feedback(f'\n ** Summary of all problem scores = \n\n \t{scores}\n')

            # Compute final score out as an integer between 0 and 1
            final_score = total_score / (len(self.sol_code) - self.sol_code.num_extra_credit())
            color = Colors.T_RED if final_score < 0.7 else Colors.T_YELLOW if final_score < 0.8 else Colors.T_DARK_GREEN if final_score < 0.9 else Colors.T_GREEN

            # Convert the final score to the scale passed by the user
            final_score = final_score * self.max_grade
            scores['final_grade'] = final_score

            # Log final scores
            stu_code.write_feedback(f'Final grade = {final_score:.2f}/{self.max_grade}')
            stu_code.log(f'Final grade = {color}{final_score:.2f}/{self.max_grade}{Colors.T_RESET}')
            return scores

    def grade_one_function(self, fn_name: str, stu_code: StudentCode):
        """Runs all test cases and grades the provided function for one specific student."""
        # Create a generator of test cases
        gen = TestCaseGenerator(fn_name, self.sol_code, stu_code)

        # Extend progress bar and keep track of test case results
        stu_code.p_bar.total = len(gen)
        stu_code.p_bar.n = 0
        test_case_results = []

        # TODO: Move to command-line?
        # How many exceptions we will allow before stopping the trials
        n_exception_patience = 5

        for trial_idx in range(len(gen)):
            stu_code.log_progress(trial_idx, len(gen))
            has_passed_test = gen[trial_idx]

            # Catch student exceptions first
            if isinstance(has_passed_test, Exception):
                n_exception_patience -= 1
                test_case_results.append(False)

                # Stop running test cases when patience runs out. If patience remains, continue to the next test case
                if n_exception_patience <= 0:
                    stu_code.write_feedback(f'# Stopping grading function early due to repeated exceptions.')
                    break
                else:
                    stu_code.write_feedback(f'# Remaining Exceptions Allowed = {n_exception_patience}')
                    continue
            # No exceptions so add pass/fail result to the total list
            test_case_results.append(has_passed_test)

        # Once all trials are completed, we compute the score between 0 and 1
        n_passed_cases = np.sum(test_case_results)
        total_score = n_passed_cases / len(gen)

        stu_code.write_feedback(f'###>>> Passed {n_passed_cases}/{len(gen)} test cases')
        stu_code.write_feedback(f'###>>> Grade for function "{fn_name}" = {total_score*100:.0f} / 100\n')
        return total_score
