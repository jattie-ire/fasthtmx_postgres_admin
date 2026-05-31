"""Authentication functions"""
import subprocess
import os


def kerberos_auth(username: str, password: str) -> bool:
    """
    Authenticate using Kerberos kinit.
    Returns True if authentication succeeds, False otherwise.
    """
    # Demo mode for testing (set SKIP_AUTH=1 environment variable)
    if os.getenv('SKIP_AUTH') == '1':
        return True
    
    try:
        # Create temporary credential cache
        ccache = f"/tmp/krb5cc_{os.getuid()}_{username}"
        env = os.environ.copy()
        env["KRB5CCNAME"] = ccache
        
        # Run kinit with username and password
        process = subprocess.Popen(
            ["kinit", f"{username}@FASTHTMX.LOCAL"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = process.communicate(input=password.encode(), timeout=5)
        
        if process.returncode == 0:
            return True
        return False
    except Exception as e:
        print(f"Auth error: {e}")
        return False
