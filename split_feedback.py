#%% Set-up
import zipfile
import pathlib
from tqdm import tqdm

# Name of exercise in _data_ whose feedback will be split
name = 'lists_exercise'

#%% Read splits
student_to_staff = {}
staff_to_student = {}
staff_list = set()
with open('split.txt', 'r') as file:
    lines = file.readlines()

assert len(lines) > 1, 'split.txt needs at least two lines'
assert lines[0].startswith('#'), 'split.txt needs to start with a staff member'

current_staff_name = ''
for line in lines:
    line = line.strip().replace('\n', '')
    if len(line) == 0:
        continue
    if line.startswith('#'):
        staff_name = line[1:]
        current_staff_name = staff_name
        staff_list.add(staff_name)

        if not staff_name in staff_to_student.keys():
            staff_to_student[staff_name] = set()
    else:
        student_name = line
        student_to_staff[student_name] = current_staff_name
        staff_to_student[current_staff_name].add(student_name)

print(staff_list)

#%% Student feedback files
for section in ['_s1', '_s2']:
    student_dir = pathlib.Path(f'_data_/{name}{section}')
    feedback_dir = student_dir / 'feedback'
    staff_to_files = {staff_name: set() for staff_name in staff_list}

    for feedback_path in feedback_dir.glob('*.bbtxt'):
        student_name = feedback_path.stem.split('_')[0]
        corresponding_staff = student_to_staff[student_name]

        staff_to_files[corresponding_staff].add(feedback_path)

    for staff_name, student_files in staff_to_files.items():
        if len(student_files) == 0:
            print(staff_name, 'has no students in this section')
            continue

        with zipfile.ZipFile(pathlib.Path('_feedback_zips_') / f'_{staff_name}_{name}.zip', 'w') as archive:
            for file in student_files:
                archive.write(file)