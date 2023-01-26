import sys
import pathlib
import subprocess
import traceback
import copy
import os
import multiprocessing
import warnings
import functools

import pandas as pd
import numpy as np
from tqdm import tqdm
from timeit import default_timer as timer


from grader.student_code import StudentCode, StudentTimeoutException, TIMEOUT_S
from grader.utils import get_module_functions, Colors
from grader.code_parser import parse_py_file

def __convert_dtype_to_regular_type__(np_type):
    if isinstance(np_type, (np.integer, np.unsignedinteger)):
        return int(np_type)
    elif isinstance(np_type, (np.inexact, np.floating)):
        return float(np_type)
    elif isinstance(np_type, (np.str_)):
        return str(np_type)
    else:
        return np_type

def compare_outputs(real_output, student_output):
    """Compares the given outputs and determines if they are equal."""
    # If we expect a 1D array and the student passes a 1D list, convert the student's list to a 1D array
    expect_1d_array = type(real_output) is np.ndarray and len(real_output.shape) == 1
    student_has_1d_list = type(student_output) is list and all([not isinstance(item, (list, np.ndarray)) for item in student_output])
    if expect_1d_array and student_has_1d_list:
        student_output = np.array(student_output, dtype=real_output.dtype)

    # Convert numpy dtypes to regular types
    real_output = __convert_dtype_to_regular_type__(real_output)
    student_output = __convert_dtype_to_regular_type__(student_output)

    # Check that the types match
    if type(real_output) != type(student_output):
        # raise StudentCodeException(f'Real solution for problem has type {type(real_solution)} but student solution has type {type(student_solution)}\n')
        return False

    # Compare the two solutions
    if type(real_output) is np.ndarray:
        return np.array_equal(real_output, student_output)
    elif type(real_output) is bool:
        return real_output == student_output
    elif type(real_output) is int or type(real_output) is float or type(real_output) is np.int32 or type(real_output) is np.float32:
        return abs(real_output - student_output) < 0.001
    elif type(real_output) is str:
        return real_output == student_output
    elif type(real_output) is list:
        return np.array_equal(real_output, student_output)
    elif type(real_output) is tuple:
        L = []
        for real_item, student_item in zip(real_output, student_output):
            L.append(compare_outputs(real_item, student_item))
        return all(L)
    elif type(real_output) is dict or type(real_output) is set:
        return real_output == student_output
    elif real_output is None:
        return student_output is None
    else:
        raise Exception(f'[Debug] Cannot grade type {type(real_output)}')

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

    def create_class_instance(self, fn_name, **constructor_kwargs):
        """Create an instance of a class from the solution module for a given function."""
        constructor_fn = self.solution_constructors[fn_name]
        if constructor_kwargs:
            return constructor_fn(**constructor_kwargs)
        else:
            return constructor_fn()

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

    def import_solution(self):
        """Imports the solution file, its functions, and its classes"""
        print('[Debug] Importing solution module')
        # Change current working directory to the solution directory for importing
        original_cwd = os.getcwd()
        os.chdir(self.solution_file.parent)

        # Import the solution file
        sol_module = __import__(self.solution_file.stem)

        # Change the working directory back to its original state
        os.chdir(original_cwd)

        # Import functions
        self.solution_fns, self.solution_constructors = get_module_functions(sol_module)

        # Check that we didn't forget to annotate a function
        # and also remove functions we do not want to grade
        to_remove = []
        for fn_name, fn in self.solution_fns.items():
            # Check for @grader.no_test_cases annotation and skip them
            if hasattr(fn, 'no_test_cases'):
                to_remove.append(fn_name)
            else:
                assert hasattr(fn, 'gen_fn_params') or hasattr(fn, 'set_fn_params'), f'[Debug] Not grading "{fn_name}" due to lack of annotation. Did you forget to annotate it?'

        for t in to_remove:
            del self.solution_fns[t]
            print(f'[Debug] Not grading {t} as it has @no_test_cases annotation')

        print(f"[Debug] Grading {len(self.solution_fns)} functions | {self.solution_fns.keys()}")

    def convert_all_student_jupyter_to_py(self):
        """Converts all student Jupyter notebooks into regular code files"""
        all_jupyter_fpaths = list(self.student_dir.glob("*.ipynb"))

        # Create a directory to place the notebooks after conversion
        if len(all_jupyter_fpaths) > 0 and not self.notebook_dir.exists():
            self.notebook_dir.mkdir()

        print('[Debug] Converting Jupyter notebooks')
        start_time = timer()
        if self.multiprocessing_cores <= 1:
            for fpath in tqdm(all_jupyter_fpaths):
                self.convert_one_student_jupyter_to_py(fpath)
        else:
            with multiprocessing.Pool(self.multiprocessing_cores) as pool:
                pool.map(self.convert_one_student_jupyter_to_py, all_jupyter_fpaths)
        print(f'[Debug] Converting Jupyter notebooks took {timer()-start_time:.2f}sec')

    def convert_one_student_jupyter_to_py(self, fpath):
        # If the file has already been converted skip it (don't convert it again!)
        if fpath.with_suffix(".py").exists():
            fpath.rename(self.notebook_dir / fpath.name)
            return

        print(f"[Auto-Grader] Converting jupyter notebook {fpath.stem} into regular code")
        subprocess.call(['jupyter', 'nbconvert', '--to', 'python', str(fpath)])

        # Move the notebook
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
            # stu_code.p_bar.total = len(self.solution_fns.keys())
            stu_code.p_bar.total = 100

            # We will keep track of all problem grades in this dictionary
            scores = {fn_name: 0 for fn_name in self.solution_fns.keys()}
            scores['student'] = stu_code.student_name

            # We will keep track of the total score from all problems in this int
            total_score = 0

            # Try to import the student's code
            import_exception = stu_code.import_module()
            scores['import_exception'] = import_exception
            if import_exception:
                stu_code.log(f'{Colors.T_MAGENTA}Import exception [{import_exception}]{Colors.T_RESET}')
                return scores

            # Go through all functions in the solution
            for idx, (fn_name, sol_fn) in enumerate(self.solution_fns.items()):
                # stu_code.p_bar.update()
                stu_code.log(f'Grading [{idx+1}/{len(self.solution_fns.keys())}], fn="{fn_name}"')
                stu_code.write_feedback(f'******************** [AutoGrader] Grading fn="{fn_name}" ********************')

                # Check if the student actually has the function
                if not stu_code.has_fn(fn_name):
                    stu_code.write_feedback(f'Did not find {fn_name} in the student code, assigning a grade of 0 to this problem')
                    scores[fn_name] = 0
                    continue

                # Grade the function
                scores[fn_name] = self.grade_one_function(fn_name, sol_fn, stu_code)
                total_score += scores[fn_name]

            # Summarize scores
            stu_code.write_feedback(f'\n ** Summary of all problem scores = \n\n \t{scores}\n')

            # Compute final score out as an integer between 0 and 1
            # TODO: Currently all problems are evenly weighted, perhaps we should allow the annotation to set the weight
            final_score = total_score / len(self.solution_fns.keys())
            color = Colors.T_RED if final_score < 0.7 else Colors.T_YELLOW if final_score < 0.8 else Colors.T_DARK_GREEN if final_score < 0.9 else Colors.T_GREEN

            # Convert the final score to the scale passed by the user
            final_score = final_score * self.max_grade
            scores['final_grade'] = final_score

            # Log final scores
            stu_code.write_feedback(f'Final grade = {final_score:.2f}/{self.max_grade}')
            stu_code.log(f'Final grade = {color}{final_score:.2f}/{self.max_grade}{Colors.T_RESET}')
            return scores

    def run_sol_fn(self, sol_fn, sol_instnc, sol_params):
        if sol_instnc:
            sol_fn = functools.partial(sol_fn, sol_instnc)

        assert isinstance(sol_params, dict), '[Debug] Solution parameters were not stored in a dictionary'
        sol_fn = functools.partial(sol_fn, **sol_params)
        
        start_t = timer()
        sol_output = sol_fn()
        end_t = timer()

        duration_sec = end_t - start_t
        return sol_output, duration_sec

    def grade_one_function(self, fn_name: str, sol_fn, stu_code: StudentCode):
        """Runs all test cases and grades the provided function for one specific student."""
        # Gather the metadata provided by the decorators
        is_class_fn = hasattr(sol_fn, 'gen_class_params')
        has_custom_equality_fn = hasattr(sol_fn, 'equality_fn')
        has_param_gen = hasattr(sol_fn, 'gen_fn_params')
        n_trials: int = sol_fn.max_trials

        # Log detailed failed cases every 1/3rd of the trials
        log_freq = max(1, n_trials // 3)
        log_next_failed_case = True

        # Extend progress bar and keep track of test case results
        stu_code.p_bar.total = n_trials
        stu_code.p_bar.n = 0
        test_case_results = []

        # How many exceptions we will allow before stopping the trials
        n_exception_patience = 5

        # Class instances for functions
        sol_instnc = None
        stu_instnc = None

        for trial_idx in range(n_trials):
            header = f'Test Case #{trial_idx+1}/{n_trials}'
            stu_code.p_bar.update()
            stu_code.log_postfix(header)

            # Check if we need to log the next failed test case
            if trial_idx % log_freq == 0:
                log_next_failed_case = True

            # Generate function parameters or get them from a fixed test set list
            if has_param_gen:
                sol_params = sol_fn.gen_fn_params()
            else:
                sol_params = sol_fn.set_fn_params[trial_idx]

            # Give the student a deep copy to decouple references which is important for some exercises
            stu_params = copy.deepcopy(sol_params)

            # Create a new class instance every X iterations of the function we are testing when testing class functions
            if is_class_fn and trial_idx % sol_fn.trials_per_instance == 0:
                stu_code.log_postfix(f'{header} | Creating classes')

                # IMPORTANT! Both classes must be initialized with the same parameters!
                class_init_params = sol_fn.gen_class_params()
                sol_instnc = self.create_class_instance(fn_name, **class_init_params)

                try:
                    stu_instnc = stu_code.create_class_instance(fn_name, **class_init_params)
                except Exception as ex:
                    stu_code.write_feedback(f'[{header}] Got exception [{ex}] when creating class {sol_instnc.__class__.__name__}. Stopping grading function early')
                    stu_code.write_feedback(f'\t{traceback.format_exc()}\n')
                    break

            # Check if we need to run the functions with an instance of a class or not
            # We also time the solution in seconds for logging later in case of student code timeouts
            stu_code.log_postfix(f'{header} | Running fns')
            sol_output, duration_sec = self.run_sol_fn(sol_fn, sol_instnc, sol_params)
            
            stu_output = stu_code.run_fn(fn_name, stu_instnc, stu_params)

            # TODO: Improve this
            def type_to_str(output):
                if type(output) is list and len(output) > 20:
                    return f'[{output[0]}, {output[1]}, ... ({len(output)-4} more items), {output[-2]}, {output[-1]}]'
                elif type(output) is dict and len(output) > 20:
                    return '{' + f'{len(output.keys())} dict items...' + '}'
                elif type(output) is set and len(output) > 20:
                    return '{' + f'{len(output)} set items...' +'}'
                else:
                    return str(output)


            def params_to_str(params: dict):

                output = ''
                for param_name, param_value in params.items():
                    output += f'{param_name}: {type_to_str(param_value)}, '

                return output[:-2]

            def output_to_str(output_all):
                if type(output_all) is tuple:
                    s = ''
                    for output in output_all:
                        s += type_to_str(output) + ', '
                    return '(' + s[:-2] + ')'
                else:
                    return type_to_str(output_all)

            # TODO: Should not print the following when the return type does not matter
            def diff_to_str(sol_output, stu_output):
                if type(sol_output) != type(stu_output):
                    if hasattr(sol_output, '__class__'):
                        sol_str = sol_output.__class__.__str__
                        # return f'Difference: Solution={sol_output} vs Student={sol_str(stu_output)}'
                        return f'Difference: The classes are not equivalent'
                    else:
                        return f'Difference: Types are different (Solution={type(sol_output)} vs Student={type(stu_output)}'
                if type(sol_output) is set:
                    return f'Difference: Items in solution but not in student = {sol_output.difference(stu_output)}, item in student but not in solution = {stu_output.difference(sol_output)}'
                elif type(sol_output) is list:
                    if len(sol_output) != len(stu_output):
                        return f'Difference: Lists are not the same length (Solution={len(sol_output)} vs Student={len(stu_output)})'
                    
                    s = 'Difference: '
                    idxs = []
                    for idx, (sol_item, stu_item) in enumerate(zip(sol_output, stu_output)):
                        if sol_item != stu_item:
                            idxs.append(idx)
                            # s += f'(IDX={idx}, Solution={sol_item}, Student={stu_item}), '
                    rand_idx = np.random.choice(idxs)
                    return f'Difference: There are [{len(idxs)}] indices that do not match. Let us see a random one -> IDX={rand_idx}, Solution[IDX] = {sol_output[rand_idx]}, Student[IDX] = {stu_output[rand_idx]}'
                else:
                    return ''

            # Check for exceptions
            if isinstance(stu_output, Exception):
                n_exception_patience -= 1
                test_case_results.append(False)

                if isinstance(stu_output, StudentTimeoutException):
                    stu_code.write_feedback(f'[{header}] Your code took too long to run so it was timed out and stopped. Remaining exceptions allowed = {n_exception_patience}')
                    stu_code.write_feedback(f'\tAs a reference, the solution took {duration_sec:.6f}s to run. The time limit is {TIMEOUT_S}s \n')
                else:
                    stu_code.write_feedback(f'[{header}] Got exception [{stu_output}] when running function {fn_name}({params_to_str(stu_params)}). Remaining exceptions allowed = {n_exception_patience}')
                    stu_code.write_feedback(f'\t{stu_code.tb}\n')

                # Stop running test cases when patience runs out. If patience remains, continue to the next test case
                if n_exception_patience <= 0:
                    stu_code.write_feedback(f'# Stopping grading function early due to repeated exceptions')
                    break
                else:
                    continue

            # Compare answers between the solution and the student
            stu_code.log_postfix(f'{header} | Checking equality')
            try:
                # Determine which comparison function we will be using
                if is_class_fn and has_custom_equality_fn:
                    has_passed_test = sol_fn.equality_fn(sol_instnc, stu_instnc, sol_output, stu_output, sol_params, stu_params)
                elif has_custom_equality_fn:
                    has_passed_test = sol_fn.equality_fn(sol_output, stu_output, sol_params, stu_params)
                else:
                    has_passed_test = compare_outputs(sol_output, stu_output)
                # Add pass/fail result to the total list
                test_case_results.append(has_passed_test)
            except Exception as ex:
                stu_code.write_feedback(f'### Got exception {ex} when grading {fn_name} when trying to compare outputs. Stopping grading early')
                stu_code.write_feedback(traceback.format_exc())
                break

            # Log failed test cases after a certain amount of iterations
            stu_code.log_postfix(f'{header} | Logging')
            if not has_passed_test and log_next_failed_case:
                log_next_failed_case = False

                stu_code.write_feedback(f'{header} failed')
                stu_code.write_feedback(f'\t The Solution Outputs -> {fn_name}({params_to_str(sol_params)})={output_to_str(sol_output)}')
                stu_code.write_feedback(f'\tYour Solution Outputs -> {fn_name}({params_to_str(stu_params)})={output_to_str(stu_output)}\n')
                stu_code.write_feedback(f'\t{diff_to_str(sol_output, stu_output)}')

                # Use our str function to print the student class
                if is_class_fn:
                    str_fn = sol_instnc.__class__.__str__
                    stu_code.write_feedback(f'\tSolution Class = \n{sol_instnc}')
                    stu_code.write_feedback(f'\tYour Class = \n{str_fn(stu_instnc)}\n')

        # Once all trials are completed, we compute the score between 0 and 1
        n_passed_cases = np.sum(test_case_results)
        total_score = n_passed_cases / n_trials

        stu_code.write_feedback(f'###>>> Passed {n_passed_cases}/{n_trials} test cases')
        stu_code.write_feedback(f'###>>> Grade for function "{fn_name}" = {total_score*100:.0f} / 100\n')
        return total_score
