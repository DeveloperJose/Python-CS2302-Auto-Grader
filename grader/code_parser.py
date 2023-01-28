from grader.student_code import StudentCode


def parse_py_file(stu_code: StudentCode):
    """Parses .py files and extracts only classes and functions.

    Does not keep comments or empty lines.
        * This allows us to add "pass" to any empty code blocks easily
        * You can always look at the original files if you want to read the comments

    Limitations:
        * Does not currently support classes within classes (could be implemented in parse_class() function)

    """
    output_lines = []
    class_dict = {}
    fn_dict = {}
    with open(stu_code.fpath, 'r') as file:
        lines = file.readlines()
        total_n_lines = len(lines)
        while len(lines) > 0:
            line = lines.pop(0)

            # Stop if we reach the end of the file
            if not line:
                break

            # Allow top-level imports
            if line.find('import') == 0:
                output_lines.append(line)

            # Top-Level Classes
            if line.find('class') == 0:
                class_spaces = __count_indentation__(line)
                key = line.strip().replace('\n', '')

                if key in class_dict.keys():
                    stu_code.write_feedback(f'[Parser] Found duplicate class [{key}], only keeping the 1st one in line {class_dict[key]}')
                    __parse_class__(None, lines, total_n_lines, class_spaces)
                    continue
                else:
                    class_dict[key] = total_n_lines - len(lines)
                    output_lines.append(line)
                    output_lines.extend(__parse_class__(stu_code, lines, total_n_lines, class_spaces))

            # Top-Level Functions
            if line.find('def') == 0:
                fn_spaces = __count_indentation__(line)
                key = line.strip().replace('\n', '')

                if key in fn_dict.keys():
                    stu_code.write_feedback(f'[Parser] Found duplicate top-level function [{key}], only keeping the 1st one in line {fn_dict[key]}')
                    __parse_function__(lines, fn_spaces)
                    continue
                else:
                    fn_dict[key] = total_n_lines - len(lines)
                    output_lines.append(line)
                    output_lines.extend(__parse_function__(lines, fn_spaces))

    with open(stu_code.fpath, 'w') as file:
        file.writelines(output_lines)


def __is_comment_or_empty__(line: str):
    """Checks if a line is a comment or empty regardless of indentation."""
    line = line.strip()  # Remove leading & trailing whitespaces from a line, ignoring indentation
    return len(line) == 0 or line[0] == '#' or line[0] == '\n'


def __count_indentation__(line: str):
    """Counts the number of leading spaces in a line."""
    return len(line) - len(line.lstrip(' '))


def __parse_class__(stu_code: StudentCode, lines: list, total_n_lines, class_spaces: int):
    output_lines = []

    fn_dict = {}
    while len(lines) > 0:
        line = lines.pop(0)

        if __is_comment_or_empty__(line):
            continue
        n_spaces = __count_indentation__(line)

        # Look for functions
        if line.find('def', n_spaces) != -1:
            key = line.strip().replace('\n', '')
            if key in fn_dict.keys():
                if stu_code:
                    stu_code.write_feedback(f'[Parser] Found function [{key}], only keeping the 1st one in line {fn_dict[key]}')
                __parse_function__(lines, n_spaces)
                continue
            else:
                fn_dict[key] = total_n_lines - len(lines)
                output_lines.append(line)

                # Find the indentation of the "def" line
                output_lines.extend(__parse_function__(lines, n_spaces))
        else:
            # It's not a function so check if we un-indented, if so, rewind file
            n_spaces = __count_indentation__(line)
            if n_spaces <= class_spaces:
                lines.insert(0, line)
                break

    # Empty class without code so add "pass" statement
    if len(output_lines) == 0:
        indentation = ' ' * (class_spaces+4)
        output_lines.append(f'{indentation}pass\n')

    return output_lines


def __parse_function__(lines: list, fn_spaces: int):
    output_lines = []

    while len(lines) > 0:
        line = lines.pop(0)
        # Ignore comments and empty lines
        if __is_comment_or_empty__(line):
            continue

        n_spaces = __count_indentation__(line)
        # Check if we un-indented and are outside of the function
        if n_spaces <= fn_spaces:
            lines.insert(0, line)
            break

        # Allow all other correctly indented lines
        output_lines.append(line)

    # Empty function without code so add "pass" statement
    if len(output_lines) == 0:
        indentation = ' ' * (fn_spaces+4)
        output_lines.append(f'{indentation}pass\n')

    return output_lines
