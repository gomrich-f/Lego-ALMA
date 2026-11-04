Lego Alma — Raspberry Pi Deploy-Anleitung

Kurz:
- Ordner `pi_deploy` enthält Skripte zum Installieren der Systemabhängigkeiten, Erzeugen eines Python-virtualenvs und Starten des Programms.

Empfohlene Schritte auf dem Raspberry Pi (im Projekt-Root-Verzeichnis):

1) Systemabhängigkeiten installieren (optional, empfohlen):

```bash
sudo bash pi_deploy/install_system_deps.sh
```

2) Python-virtualenv erstellen und Python-Pakete installieren:

```bash
bash pi_deploy/setup_pi.sh
```

3) Programm starten:

```bash
bash pi_deploy/start.sh
```

Hinweise:
- `requirements.txt` listet die erkannten Python-Abhängigkeiten: numpy, scipy, matplotlib, astropy, Pillow, opencv-python, pyserial, tqdm, tenacity.
- Modul `decawave_ble` scheint projekt- oder hardware-spezifisch zu sein und ist möglicherweise nicht auf PyPI verfügbar. Wenn `pip install -r requirements.txt` für `decawave_ble` fehlschlägt, lies die Projektdokumentation oder kontaktiere den Hardware-Anbieter für Installationsanweisungen.
- Wenn `opencv-python` auf dem Pi Probleme macht, verwende `opencv-python-headless` oder installiere OpenCV über apt/apt-get vor dem `pip install`.

Systemd-Auto-Start (optional):
- Kopiere `pi_deploy/lego_alma.service` nach `/etc/systemd/system/` und passe `User` und Pfade an.

```bash
sudo cp pi_deploy/lego_alma.service /etc/systemd/system/lego_alma.service
sudo systemctl daemon-reload
sudo systemctl enable lego_alma.service
sudo systemctl start lego_alma.service
```

Wenn du möchtest, passe ich die Service-Datei an deine genaue Pi-Pfadstruktur oder versuche, `decawave_ble` und weitere hardware-spezifische Pakete automatisch zu erkennen und einzubauen.
