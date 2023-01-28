import numpy as np
import inspect

# Functions that don't require @no_test_cases to be ignored
IGNORED_FUNCTIONS = {'__init__', 'draw'}


class Colors:
    # Terminal Colors (https://chrisyeh96.github.io/2020/03/28/terminal-colors.html)
    T_RED = '\033[91m'
    T_GREEN = '\033[92m'
    T_YELLOW = '\033[93m'
    T_BLUE = '\033[94m'
    T_MAGENTA = '\033[95m'
    T_CYAN = '\033[96m'

    T_RESET = '\033[0m'
    T_LIGHT_GREEN = '\033[92;1m'
    T_DARK_GREEN = '\033[92;2m'
    T_DARK_RED = '\033[91;2m'
    T_DARK_YELLOW = '\033[93;2m'


def get_module_functions(module):
    """
    Gets all the functions in the module and all class constructors.

    Ignores class constructors and functions named draw() without requiring annotation.
    """
    # First get all module functions that are not inside a class
    fns = dict(inspect.getmembers(module, inspect.isfunction))

    # Get the classes if any and extract their functions
    # TODO: Remove imported classes
    classes = inspect.getmembers(module, inspect.isclass)
    constructors = {}

    # print(f"[Debug] Inspected classes = {classes}")
    ignored = {'tqdm', 'scipy'}
    for class_name, class_obj in classes:
        if class_name in ignored:
            continue
        for orig_fn_name, fn in inspect.getmembers(class_obj, inspect.isfunction):
            # Combine class name with function name to use as key for dictionary
            fn_name = f'{class_name}.{orig_fn_name}()'
            if orig_fn_name in IGNORED_FUNCTIONS:
                print(f'[Debug] Not grading {fn_name} as they are in the ignore set')
                continue
            assert fn_name not in fns.keys(), f'Two functions have the same name, {fn_name}'
            fns[fn_name] = fn
            constructors[fn_name] = class_obj

    return fns, constructors
