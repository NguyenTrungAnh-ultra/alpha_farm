import os
import re

root_dir = r"f:\Projects\alpha_farm"

for folder, _, files in os.walk(root_dir):
    if '.git' in folder or 'venv' in folder or '__pycache__' in folder or 'results' in folder:
        continue
    for file in files:
        if file.endswith('.py') and file != 'AppConfig.py':
            path = os.path.join(folder, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove sys.path hacks
            new_content = re.sub(r'PROJECT_ROOT\s*=\s*.*?[\r\n]+', '', content)
            new_content = re.sub(r'if PROJECT_ROOT not in sys\.path:[\r\n]+\s*sys\.path\.insert\(0, PROJECT_ROOT\)[\r\n]+', '', new_content)
            
            # If the file used PROJECT_ROOT, add import at the top
            if 'PROJECT_ROOT' in new_content:
                if 'from utilities.AppConfig import PROJECT_ROOT' not in new_content:
                    new_content = 'from utilities.AppConfig import PROJECT_ROOT\n' + new_content
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Cleaned {path}")
