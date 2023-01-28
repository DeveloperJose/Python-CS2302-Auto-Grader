import numpy as np


def convert_np_dtype_to_regular_type(np_type):
    """Converts numpy dtypes to regular Python types."""
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
    real_output = convert_np_dtype_to_regular_type(real_output)
    student_output = convert_np_dtype_to_regular_type(student_output)

    # Check that the types match
    if type(real_output) != type(student_output):
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


def type_to_str(output):
    """Converts the specified output into a more readable string format."""
    # TODO: Improve this
    if type(output) is list and len(output) > 20:
        return f'[{output[0]}, {output[1]}, ... ({len(output)-4} more items), {output[-2]}, {output[-1]}]'
    elif type(output) is dict and len(output) > 20:
        return '{' + f'{len(output.keys())} dict items...' + '}'
    elif type(output) is set and len(output) > 20:
        return '{' + f'{len(output)} set items...' + '}'
    else:
        return str(output)


def params_to_str(params: dict):
    """Converts a function parameter dictionary into a more readable string format."""
    output = ''
    for param_name, param_value in params.items():
        output += f'{param_name}: {type_to_str(param_value)}, '

    return output[:-2]


def output_to_str(output_all):
    """Converts function outputs into a more readable string format."""
    if type(output_all) is tuple:
        s = ''
        for output in output_all:
            s += type_to_str(output) + ', '
        return '(' + s[:-2] + ')'
    else:
        return type_to_str(output_all)


def diff_to_str(sol_output, stu_output):
    """Finds out a human readable string specifying what the differences are between the specified outputs."""
    # TODO: Should not print the following when the return type does not matter
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
