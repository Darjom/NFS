import subprocess

def run_command(cmd, check=False):

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    out, err = p.communicate()
    if check and p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd, output=out, stderr=err)
    return p.returncode, out.strip(), err.strip()
