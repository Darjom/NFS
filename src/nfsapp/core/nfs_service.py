from ..utils.shell import run_command

def ensure_nfs_active():
    # habilita e inicia nfs-server
    run_command(["/usr/bin/systemctl", "enable", "--now", "nfs-server"])

def apply_exports():
    """
    Aplica los cambios de /etc/exports usando exportfs.
    """
    # usa la ruta completa
    rc, out, err = run_command(["/usr/sbin/exportfs", "-ra"])
    # recarga el servicio para asegurarse
    run_command(["/usr/bin/systemctl", "reload", "nfs-server"])
    return rc, out, err

def open_firewall_services():
    """
    Opcional: abre los puertos necesarios si firewalld existe.
    """
    rc, _, _ = run_command(["/usr/bin/which", "firewall-cmd"])
    if rc == 0:
        run_command(["/usr/bin/firewall-cmd", "--add-service=nfs", "--permanent"])
        run_command(["/usr/bin/firewall-cmd", "--add-service=rpc-bind", "--permanent"])
        run_command(["/usr/bin/firewall-cmd", "--reload"])
