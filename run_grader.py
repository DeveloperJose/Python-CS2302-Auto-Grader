# ███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████
#
# ▄████████    ▄████████         ▄████████ ███    █▄      ███      ▄██████▄     ▄██████▄     ▄████████    ▄████████ ████████▄     ▄████████    ▄████████
# ███    ███   ███    ███        ███    ███ ███    ███ ▀█████████▄ ███    ███   ███    ███   ███    ███   ███    ███ ███   ▀███   ███    ███   ███    ███
# ███    █▀    ███    █▀         ███    ███ ███    ███    ▀███▀▀██ ███    ███   ███    █▀    ███    ███   ███    ███ ███    ███   ███    █▀    ███    ███
# ███          ███               ███    ███ ███    ███     ███   ▀ ███    ███  ▄███         ▄███▄▄▄▄██▀   ███    ███ ███    ███  ▄███▄▄▄      ▄███▄▄▄▄██▀
# ███        ▀███████████      ▀███████████ ███    ███     ███     ███    ███ ▀▀███ ████▄  ▀▀███▀▀▀▀▀   ▀███████████ ███    ███ ▀▀███▀▀▀     ▀▀███▀▀▀▀▀
# ███    █▄           ███        ███    ███ ███    ███     ███     ███    ███   ███    ███ ▀███████████   ███    ███ ███    ███   ███    █▄  ▀███████████
# ███    ███    ▄█    ███        ███    ███ ███    ███     ███     ███    ███   ███    ███   ███    ███   ███    ███ ███   ▄███   ███    ███   ███    ███
# ████████▀   ▄████████▀         ███    █▀  ████████▀     ▄████▀    ▀██████▀    ████████▀    ███    ███   ███    █▀  ████████▀    ██████████   ███    ███
#                                                                                         ███    ███                                        ███    ███
#
# ██████████ by Jose G. Perez <DeveloperJose> ███████████████████████████████████████████████████████████████████████████████████████████████████████████
# ██████████████ Last Modified: 07/05/2022 ██████████████████████████████████████████████████████████████████████████████████████████████████████████████
# Limitations:

# Notes:
#   * If you want students to see their mistakes more easily implement the __str__() and __repr__() functions for your classes
#   * Features command-line colors!
# Grading Pipeline:
#   1. Prepare grader by parsing command-line arguments and creating directories to be used later
#   2. Override some libraries we don't want to run while grading such as matplotlib's show() or Colab's file.upload()
#   3. Import the solution file functions and classes
#   4. Convert jupyter .ipynb notebooks to .py files
#   5. Grade all student code files
#       * Parses .py to extract only functions and classes, removing everything else, and writing "pass" to any empty classes/functions to try and make the code run
# General Todo List:
#   TODO: Figure out if we can get timeout to work on Windows
#   TODO: Allow each problem to have its own max_score
#   TODO: Allow each problem to set its weight relative to the final score
#   TODO: Allow each problem to pass timeout_s instead of defining a single one
#   TODO: Allow for extra credit
import pathlib
import argparse
import zipfile
from timeit import default_timer as timer


from grader import Grader


def is_code_file(file_str):
    return file_str[-3:] == '.py' or file_str[-6:] == '.ipynb'


if __name__ == '__main__':

    # Parse arguments from the command-line
    parser = argparse.ArgumentParser()
    parser.add_argument('-sol', '--solution_file', type=pathlib.Path, required=True)
    parser.add_argument('-sd', '--student_dir', type=pathlib.Path, required=False)
    parser.add_argument('-mg', '--max_grade', type=float, required=False, default=100)
    parser.add_argument('-mp', '--multiprocessing', type=int, required=False, default=1)
    parser.add_argument('-s', '--students', nargs='+', required=False)
    args = parser.parse_args()

    print("""
        ███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████

        ▄████████    ▄████████         ▄████████ ███    █▄      ███      ▄██████▄     ▄██████▄     ▄████████    ▄████████ ████████▄     ▄████████    ▄████████ 
        ███    ███   ███    ███        ███    ███ ███    ███ ▀█████████▄ ███    ███   ███    ███   ███    ███   ███    ███ ███   ▀███   ███    ███   ███    ███ 
        ███    █▀    ███    █▀         ███    ███ ███    ███    ▀███▀▀██ ███    ███   ███    █▀    ███    ███   ███    ███ ███    ███   ███    █▀    ███    ███ 
        ███          ███               ███    ███ ███    ███     ███   ▀ ███    ███  ▄███         ▄███▄▄▄▄██▀   ███    ███ ███    ███  ▄███▄▄▄      ▄███▄▄▄▄██▀ 
        ███        ▀███████████      ▀███████████ ███    ███     ███     ███    ███ ▀▀███ ████▄  ▀▀███▀▀▀▀▀   ▀███████████ ███    ███ ▀▀███▀▀▀     ▀▀███▀▀▀▀▀   
        ███    █▄           ███        ███    ███ ███    ███     ███     ███    ███   ███    ███ ▀███████████   ███    ███ ███    ███   ███    █▄  ▀███████████ 
        ███    ███    ▄█    ███        ███    ███ ███    ███     ███     ███    ███   ███    ███   ███    ███   ███    ███ ███   ▄███   ███    ███   ███    ███ 
        ████████▀   ▄████████▀         ███    █▀  ████████▀     ▄████▀    ▀██████▀    ████████▀    ███    ███   ███    █▀  ████████▀    ██████████   ███    ███ 
                                                                                                ███    ███                                        ███    ███ 

        ██████████ by Jose G. Perez <DeveloperJose> ███████████████████████████████████████████████████████████████████████████████████████████████████████████
    """)

    assert args.solution_file.exists(), f'--solution_file {args.solution_file} does not exist'

    if not args.student_dir:
        # Try to find the student directory from the solution filename. We'll try
        # 1. The stem of the solution file (filename without extension)
        # 2. The stem of the solution file with the string "_solution" removed
        possible_dirnames = [args.solution_file.stem, args.solution_file.stem.replace('_solution', '')]

        # Try looking for the directory
        found_dir = False
        for dirname in possible_dirnames:
            possible_student_dir = pathlib.Path('_data_') / dirname
            if possible_student_dir.exists():
                args.student_dir = possible_student_dir
                found_dir = True
                break

        # If we didn't find the directory, try searching for the Blackboard zip file
        if not found_dir:
            for dirname in possible_dirnames:
                possible_zip = pathlib.Path('_data_') / (dirname + '.zip')
                possible_student_dir: pathlib.Path = pathlib.Path('_data_') / dirname

                # The zipfile exists, so extract the code files
                if possible_zip.exists():
                    with zipfile.ZipFile(possible_zip, 'r') as zip_ref:
                        print(f'[Debug] Extracting {possible_zip} to {possible_student_dir}')
                        filenames = [fname for fname in zip_ref.namelist() if is_code_file(fname)]
                        zip_ref.extractall(possible_student_dir, filenames)

                        args.student_dir = possible_student_dir
                        break

        assert args.student_dir, f'Could not find student_dir automatically, please pass it with --student_dir'
    else:
        assert args.student_dir.exists(), f'--student_dir {args.student_dir} does not exist'

    # Grading Pipeline
    print(f'[Debug] Grading {args.solution_file} with student code located at {args.student_dir}')
    print(f'[Debug] Complete Args = {args}')

    start_time = timer()
    grader = Grader(args)
    grader.override_libraries()
    grader.import_solution()
    grader.convert_all_student_jupyter_to_py()
    grader.grade_all_students()
    end_time = timer()

    print(f'Finished grading! Grading took {end_time - start_time:.2f}s')

    if 'import_exception' in grader.df.keys():
        df = grader.df[grader.df['import_exception'] == True]
        print(f"Could not import the following students's code even after running code_parser")
        print(df['student'].values)
