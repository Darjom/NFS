# NFS Configurator

Aplicación de escritorio desarrollada en Python (OpenSUSE 15.6) para gestionar y configurar el servicio **NFS (Network File System)**.

## Entorno

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/nfsconfig/main.py
sudo -E env PYTHONPATH=/home/.../Desktop/nfs /home/.../Desktop/nfs/.venv/bin/python -m src.nfsapp.main
sudo firewall-cmd --add-service=mountd --permanent
sudo firewall-cmd --reload
