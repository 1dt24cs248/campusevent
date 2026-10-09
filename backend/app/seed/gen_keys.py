import os
import secrets
from cryptography.fernet import Fernet

def generate_keys():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    jwt_secret = secrets.token_urlsafe(32)
    fernet_key = Fernet.generate_key().decode()
    
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
    else:
        with open(env_path + ".example", 'r') as f:
            env_content = f.read()
            
    lines = env_content.split('\n')
    new_lines = []
    has_jwt = False
    has_enc = False
    for line in lines:
        if line.startswith('JWT_SECRET='):
            new_lines.append(f'JWT_SECRET={jwt_secret}')
            has_jwt = True
        elif line.startswith('APP_ENCRYPTION_KEY='):
            new_lines.append(f'APP_ENCRYPTION_KEY={fernet_key}')
            has_enc = True
        else:
            new_lines.append(line)
            
    if not has_jwt:
        new_lines.append(f'JWT_SECRET={jwt_secret}')
    if not has_enc:
        new_lines.append(f'APP_ENCRYPTION_KEY={fernet_key}')
        
    with open(env_path, 'w') as f:
        f.write('\n'.join(new_lines))
    print("Generated JWT_SECRET and APP_ENCRYPTION_KEY in .env")

if __name__ == "__main__":
    generate_keys()
