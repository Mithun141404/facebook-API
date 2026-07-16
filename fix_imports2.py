from typing import List, Optional, Dict, Any
import os

def fix_imports(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    
    # Remove the bad imports I inserted
    lines = [l for l in lines if l != 'from typing import List, Optional, Dict, Any']
    
    # Insert safely at the top
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('from __future__'):
            insert_idx = i + 1
            break
            
    lines.insert(insert_idx, "from typing import List, Optional, Dict, Any")
    
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Fixed {filepath}")

for root, dirs, files in os.walk('/home/legend/Desktop/facebook-api'):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            fix_imports(os.path.join(root, file))
