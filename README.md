# NFS Configurator

Aplicación de escritorio desarrollada en Python (OpenSUSE 15.6) para gestionar y configurar el servicio **NFS (Network File System)**.

## Requisitos e instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Dependencias del sistema

Ejecutar script:

```bash
chmod +x scripts/install_qt_runtime_suse.sh
./scripts/install_qt_runtime_suse.sh
```

## Instalar y habilitar NFS

```bash
sudo zypper -n in nfs-kernel-server
sudo systemctl enable --now nfs-server
sudo firewall-cmd --add-service=nfs --permanent
sudo firewall-cmd --add-service=mountd --permanent
sudo firewall-cmd --add-service=rpc-bind --permanent
sudo firewall-cmd --reload
```

## Ejecutar aplicación

```bash
sudo -E env PYTHONPATH=/home/.../Desktop/nfs /home/.../Desktop/nfs/.venv/bin/python -m src.nfsapp.main

sudo -E bash -c 'cd /home/.../Desktop/nfs && /home/.../Desktop/nfs/.venv/bin/python -m src.nfsapp.main'
```

## Sqash check

poner en  extras esto si seleccional el rot_sqash
```bash
anonuid=1000,anongid=100
```
