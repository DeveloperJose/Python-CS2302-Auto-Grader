import os
import traceback
import sys
import pathlib
import functools

from tqdm import tqdm
import wrapt_timeout_decorator

from grader.utils import get_module_functions, Colors

TIMEOUT_S = 8  # 0.1  # How many seconds should we allow student functions to run before terminating them


class StudentTimeoutException(Exception):
    """Exception that is raised when a student function takes too long to run and is timed out."""
    pass


class SilenceOutput:
    """Silences stdout. Useful to ignore student print() statements."""

    def __init__(self):
        self.stdout = sys.stdout

    def __enter__(self):
        sys.stdout = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.stdout


class StudentCode:
    def __init__(self, student_dir: pathlib.Path, student_fpath: pathlib.Path, all_student_files: list):
        self.student_dir = student_dir
        self.fpath = student_fpath
        self.all_student_files = all_student_files

        assert self.fpath.exists(), f'Student file {student_fpath} does not exist'
        assert len(all_student_files) > 0, 'Student files must be positive'

        self.feedback_dir = self.student_dir / 'feedback'
        assert self.feedback_dir.exists(), f'Student feedback directory {self.feedback_dir} does not exist. Was "Grader" unable to __init__ correctly?'

        self.header = ''

    def __enter__(self):
        # Determine if it's a Blackboard bulk download file in the format
        # {assignment name}_{student username}_attempt_{date}_{filename}
        split_filename = self.fpath.stem.split('_')
        is_bulk_blackboard = len(split_filename) >= 4

        # If it's a Blackboard file, sort all attempts based on date and assign this attempt a simple number
        # for the feedback output file. Otherwise make the feedback output file the same name as the attempt file
        if is_bulk_blackboard:
            student_name = split_filename[1]
            date = split_filename[3]

            # Gather and then sort all Blackboard attempts based on date
            other_attempt_dates = []
            for att_path in self.all_student_files:
                split_att_path = att_path.stem.split('_')
                if len(split_att_path) < 4 or split_att_path[1] != student_name:
                    continue
                other_attempt_dates.append(split_att_path[3])
            other_attempt_dates = sorted(other_attempt_dates)

            attempt_number = other_attempt_dates.index(date)+1

            self.feedback_filename = f'{student_name}_attempt{attempt_number}.bbtxt'
            self.student_name = f'{student_name}_{attempt_number}'
            # print(f'[Auto-Grader] Grading {self.student_name} blackboard attempt {attempt_number} / {len(other_attempt_dates)}')
        else:
            self.feedback_filename = f'{self.fpath}.bbtxt'
            self.student_name = f'{self.fpath.stem}'
            # print(f'[Auto-Grader] Grading {self.student_name} attempt')

        # Open the feedback file and progress bar
        self.feedback = open(self.feedback_dir / self.feedback_filename, 'w')
        self.p_bar = tqdm()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.write_feedback(f'[AutoGrader: StudentCode] Got exception type [{exc_type}] with value [{exc_val}], unable to proceed with grading')
            self.write_feedback(traceback.format_tb(exc_tb))
            self.log(f'{Colors.T_MAGENTA}StudentCode() exited with exception {exc_type} [{exc_val}]{Colors.T_RESET}')

        self.feedback.close()

        self.p_bar.n = self.p_bar.total
        self.p_bar.close()

    def import_module(self):
        """Imports the student module, its functions, and the class constructors."""
        import_exception = None
        # Change current working directory to the solution directory for importing
        original_cwd = os.getcwd()
        os.chdir(self.fpath.parent)
        with SilenceOutput():
            try:
                module = __import__(self.fpath.stem)
                self.fns, self.constructors = get_module_functions(module)
            except Exception as ex:
                self.write_feedback(f'[AutoGrader] Could not import module due to exception {ex}')
                self.write_feedback(traceback.format_exc())
                import_exception = ex

        # Change the working directory back to its original state
        os.chdir(original_cwd)
        return import_exception

    def write_feedback(self, msg):
        """Writes feedback to the student output file."""
        assert hasattr(self, 'feedback'), f'You must use the with statement when using this class'

        n_bytes = self.feedback.tell()
        bytes_in_mb = 1e6
        mb_max = 10
        if n_bytes < mb_max * bytes_in_mb:
            self.feedback.write(f'{msg}\n')
        else:
            raise Exception(f'[Debug] Student {self.student_name} has more than {mb_max}MBs of feedback')

    def log(self, msg):
        """Writes a log to the student progress bar"""
        self.p_bar.desc = f'[{self.student_name}] {msg}'

    def log_postfix(self, msg):
        self.p_bar.postfix = f'{Colors.T_CYAN}{self.header} | {msg}{Colors.T_RESET}'

    def log_progress(self, trial_idx, n_trials):
        self.header = f'Test Case #{trial_idx+1}/{n_trials}'

    def has_fn(self, fn_name):
        """Determines if the given function name is in the student code"""
        return fn_name in self.fns.keys()

    def run_fn(self, fn_name, stu_instnc, stu_params):
        """Runs the provided function given the function name."""
        assert hasattr(self, 'fns'), 'You must call import_module() first before calling run_fn'

        if fn_name not in self.fns.keys():
            raise Exception(f'Did not find {fn_name} in the student code')

        stu_fn = self.fns[fn_name]

        # If a class instance is provided, wrap as a partial function
        if stu_instnc:
            stu_fn = functools.partial(stu_fn, stu_instnc)
            stu_fn = functools.wraps(self.fns[fn_name])(stu_fn)

        with SilenceOutput():
            return self.__run_fn_timeout__(stu_fn, **stu_params)

    def create_class_instance(self, fn_name, **constructor_kwargs):
        """Creates an instance of the class needed to run the provided function."""
        if fn_name not in self.constructors.keys():
            raise Exception(f'Function {fn_name} was expected to be inside a class but it was not')

        constructor_fn = self.constructors[fn_name]
        with SilenceOutput():
            if constructor_kwargs:
                return constructor_fn(**constructor_kwargs)
            else:
                return constructor_fn()

    def __run_fn_timeout__(self, fn, *args, **kwargs):
        """Runs the given function with a time limit."""
        try:
            return wrapt_timeout_decorator.timeout(TIMEOUT_S, use_signals=True, timeout_exception=StudentTimeoutException)(fn)(*args, **kwargs)
        except StudentTimeoutException as ex:
            self.tb = traceback.format_exc()
            return ex
        except OSError as ex:
            self.tb = traceback.format_exc()
            return ex
        except Exception as ex:
            self.tb = traceback.format_exc()
            return ex