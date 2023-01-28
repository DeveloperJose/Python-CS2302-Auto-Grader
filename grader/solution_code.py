import os
import functools
import pathlib

from timeit import default_timer as timer

from grader.utils import get_module_functions


class SolutionCode:
    def __init__(self, solution_file: pathlib.Path):
        """Imports the solution file, its functions, and its classes"""

        # Change current working directory to the solution directory for importing
        print('[Debug] Importing solution module')
        original_cwd = os.getcwd()
        os.chdir(solution_file.parent)

        # Import the solution file
        sol_module = __import__(solution_file.stem)

        # Change the working directory back to its original state
        os.chdir(original_cwd)

        # Import functions
        self.solution_fns, self.solution_constructors = get_module_functions(sol_module)

        # Check that we didn't forget to annotate a function and also remove functions we do not want to grade
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

        # Open the solution file to sort the functions by order of appearance
        # with open(solution_file, 'r') as file:
        #     for idx, line in enumerate(file.readlines()):
        #         line = line.strip()
        #         if not line.startswith('def '):
        #             continue
        #         func_name = line[4:line.index('(')]

        self.all_fnames = list(self.solution_fns.keys())
        print(f"[Debug] Grading {len(self.solution_fns)} functions | {self.all_fnames}")

    def run_fn(self, fn_name, sol_instnc, sol_params):
        """Runs and times the specified solution function with the specified parameters."""
        sol_fn = self.solution_fns[fn_name]
        if sol_instnc:
            sol_fn = functools.partial(sol_fn, sol_instnc)

        assert isinstance(sol_params, dict), '[Debug] Solution parameters were not stored in a dictionary'

        start_t = timer()
        sol_output = sol_fn(**sol_params)
        end_t = timer()

        duration_sec = end_t - start_t
        return sol_output, duration_sec

    def create_fn_parameters(self, fn_name, trial_idx):
        """Generates function parameters for the specified function or gets them from a fixed test set list."""
        sol_fn = self.solution_fns[fn_name]
        has_param_gen = hasattr(sol_fn, 'gen_fn_params')
        if has_param_gen:
            return sol_fn.gen_fn_params()
        else:
            return sol_fn.set_fn_params[trial_idx]

    def create_class_instance(self, fn_name):
        """Creates an instance of a class from the solution module for a given function."""
        sol_fn = self.solution_fns[fn_name]
        sol_constructor_fn = self.solution_constructors[fn_name]

        # Generate parameters for __init__ function.
        sol_class_init_params = sol_fn.gen_class_params()

        # Run the solution class constructor
        if sol_class_init_params:
            sol_instnc = sol_constructor_fn(**sol_class_init_params)
        else:
            sol_instnc = sol_constructor_fn()

        return sol_instnc, sol_class_init_params

    def __len__(self):
        """Counts how many gradeable functions there are in this solution file."""
        return len(self.all_fnames)

    def __getitem__(self, fn_idx):
        """Gets the specified function from this solution file. Can be an index or a function name string."""
        if isinstance(fn_idx, int):
            fn_name = self.all_fnames[fn_idx]
        elif isinstance(fn_idx, str):
            fn_name = fn_idx
        else:
            raise Exception(f'fn_idx must be an integer index or function string name')

        fn = self.solution_fns[fn_name]
        return fn_name, fn

    def num_extra_credit(self):
        """Counts the number of gradable extra credit problems in the solution file."""
        return sum([hasattr(fn, 'extra_credit') for _, fn in self])
