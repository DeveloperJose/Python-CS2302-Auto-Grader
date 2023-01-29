import copy
import traceback


from grader.student_code import StudentCode, StudentTimeoutException, TIMEOUT_S
from grader.feedback import params_to_str, output_to_str, diff_to_str, compare_outputs

class TestCaseGenerator:
    def __init__(self, fn_name, sol_code, stu_code: StudentCode):
        self.fn_name = fn_name
        self.sol_code = sol_code
        self.stu_code = stu_code

        # Gather metadata provided by the decorators
        self.sol_fn = self.sol_code.solution_fns[fn_name]
        self.is_class_fn = hasattr(self.sol_fn, 'gen_class_params')
        self.has_equality_fn = hasattr(self.sol_fn, 'equality_fn')
        self.max_trials = self.sol_fn.max_trials
        self.is_extra_credit = hasattr(self.sol_fn, 'extra_credit')

        if self.is_class_fn:
            self.trials_per_instance = self.sol_fn.trials_per_instance

        # Class instances for functions
        self.sol_instnc = None
        self.stu_instnc = None

        # Log detailed failed cases every 1/3rd of the trials
        self.log_freq = max(1, self.max_trials // 3)
        self.log_next_failed_case = True

    def __len__(self):
        """Counts the number of test cases that can be generated for the given function."""
        return self.max_trials
    
    def __getitem__(self, trial_idx):
        """
        Generates the given test case number (trial_idx) and returns a boolean representing if the test passed or not.

        Returns True/False when the given test case passed or failed.
        Returns an Exception when the student code fails.
        """
        # Log detailed failed cases every 1/3rd of the trials
        if trial_idx % self.log_freq == 0:
            self.log_next_failed_case = True

        # Generate parameters for test case. Give student deep copy to decouple references
        sol_params = self.sol_code.create_fn_parameters(self.fn_name, trial_idx)
        stu_params = copy.deepcopy(sol_params)

        # Generate solution/student class instances every X iterations of the function when testing class functions
        if self.is_class_fn and trial_idx % self.trials_per_instance == 0:
            self.stu_code.log_postfix('Creating classes')

            # IMPORTANT! Both classes must be initialized with the same parameters!
            # Give student deep copy to decouple references
            self.sol_instnc, sol_class_init_params = self.sol_code.create_class_instance(self.fn_name)
            stu_class_init_params = copy.deepcopy(sol_class_init_params)

            # Run the student class constructor
            try:
                self.stu_instnc = self.stu_code.create_class_instance(self.fn_name, **stu_class_init_params)
            except Exception as ex:
                self.stu_code.write_feedback(f'Got exception [{ex}] when creating class {self.sol_instnc.__class__.__name__}')
                return ex

        # Run and time solution function
        self.stu_code.log_postfix('Running fns')
        sol_output, sol_duration_sec = self.sol_code.run_fn(self.fn_name, self.sol_instnc, sol_params)

        # Try to run student function
        try:
            stu_output = self.stu_code.run_fn(self.fn_name, self.stu_instnc, stu_params)
        except StudentTimeoutException as ex:
            self.stu_code.write_feedback(f'Your code took too long to run so it was timed out and stopped.')
            self.stu_code.write_feedback(f'\tAs a reference, the solution took {sol_duration_sec:.6f}s to run. The time limit is {TIMEOUT_S}s \n')
            return ex
        except Exception as ex:
            self.stu_code.write_feedback(f'Got exception [{ex}] when running function {self.fn_name}({params_to_str(stu_params)}).')
            self.stu_code.write_feedback(f'\t{self.stu_code.tb}\n')
            return ex
        
        # Compare answers between the solution and the student
        self.stu_code.log_postfix(f'Checking equality')
        try:
            # Determine which comparison function we will be using
            if self.is_class_fn and self.has_equality_fn:
                has_passed_test = self.sol_fn.equality_fn(self.sol_instnc, self.stu_instnc, sol_output, stu_output, sol_params, stu_params)
            elif self.has_equality_fn:
                has_passed_test = self.sol_fn.equality_fn(sol_output, stu_output, sol_params, stu_params)
            else:
                has_passed_test = compare_outputs(sol_output, stu_output)
        except Exception as ex:
            self.stu_code.write_feedback(f'### Got exception {ex} when grading {self.fn_name} when trying to compare outputs.')
            self.stu_code.write_feedback(traceback.format_exc())
            return ex
        
        # Check if we need to log the next failed test case
        if not has_passed_test and self.log_next_failed_case:
            self.log_next_failed_case = False
            self.stu_code.log_postfix(f'Logging')

            # Only print the output differences when we are not using a custom comparer function
            # Fixes Hassan's comment about not needing to print when output return type doesn't matter
            if not self.has_equality_fn:
                self.stu_code.write_feedback(f'Test Case #{trial_idx+1} failed | Reason => {diff_to_str(sol_output, stu_output)}')
                self.stu_code.write_feedback(f'\t The Solution Outputs -> {self.fn_name}({params_to_str(sol_params)})={output_to_str(sol_output)}')
                self.stu_code.write_feedback(f'\tYour Solution Outputs -> {self.fn_name}({params_to_str(stu_params)})={output_to_str(stu_output)}')
                self.stu_code.write_feedback(f'')
            else:
                self.stu_code.write_feedback(f'Test Case #{trial_idx+1} failed')

            # Use our str function to print the student class
            if self.is_class_fn:
                str_fn = self.sol_instnc.__class__.__str__
                self.stu_code.write_feedback(f'\tSolution Class = \n{self.sol_instnc}')
                self.stu_code.write_feedback(f'\tYour Class = \n{str_fn(self.stu_instnc)}\n')

        return has_passed_test
