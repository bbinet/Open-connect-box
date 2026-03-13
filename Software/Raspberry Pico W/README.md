---

# Installation du Firmware MicroPython sur RP2040 avec ESP8285 (Pico W Clone)

Ce guide vous explique comment installer le firmware MicroPython sur une carte RP2040 avec ESP8285 (clone Pico W) et comment ajouter les fichiers Python disponibles dans le dossier `uAldes`.

---

## Important: Clone Pico W vs Pico W Original

Cette version est conçue pour les **clones de Pico W** qui utilisent:
- **RP2040** comme microcontrôleur
- **ESP8285** comme puce WiFi (au lieu du CYW43439 sur le Pico W original)

Ces cartes nécessitent une approche différente car l'ESP8285 communique via UART avec des commandes AT, tandis que le CYW43439 du Pico W original utilise SPI et une API native.

---

## Prérequis

Avant de commencer, assurez-vous d'avoir les éléments suivants :

- Une carte RP2040 avec ESP8285 (clone Pico W)
- Un câble micro-USB
- Un ordinateur Linux
- Le firmware MicroPython pour **RP2040 standard** (PAS la version Pico W)
- L'outil `mpremote` pour transférer les fichiers

---

## Étapes d'installation du Firmware MicroPython

### 1. Téléchargez le Firmware

```bash
wget https://micropython.org/resources/firmware/RPI_PICO-20250911-v1.26.1.uf2
```

> **Note**: N'utilisez PAS le firmware `RPI_PICO_W-*.uf2` car il est conçu pour le CYW43439. Utilisez `RPI_PICO-*.uf2` pour les clones avec ESP8285.

### 2. Installez le Firmware sur la carte

```bash
# Connectez la carte en maintenant le bouton BOOTSEL enfoncé
# Vérifiez le device attribué
lsblk

# Copiez le firmware directement sur le device (adaptez /dev/sdX1)
sudo cp RPI_PICO-20250911-v1.26.1.uf2 /dev/sdc1

# La carte redémarre automatiquement avec MicroPython installé
```

---

## Ajouter des Fichiers Python depuis le Dossier `uAldes`

### 1. Installez mpremote

```bash
# Avec pip
pip install mpremote

# Ou avec nix
nix-shell -p mpremote
```

> **Note** : Si vous n'avez pas accès au port série, ajoutez votre utilisateur au groupe `dialout` :
> ```bash
> sudo usermod -a -G dialout $USER
> # Puis déconnectez-vous et reconnectez-vous
> ```

### 2. Fichiers à transférer

Les fichiers suivants sont nécessaires:

| Fichier | Description |
|---------|-------------|
| `main.py` | Script principal |
| `config.py` | Configuration (WiFi, MQTT, HTTP, hardware) |
| `espicoW.py` | Driver WiFi pour ESP8285 |
| `simple_esp.py` | Client MQTT pour ESP8285 (optionnel si MQTT désactivé) |
| `http_server.py` | Serveur HTTP pour API REST |
| `ualdes.py` | Bibliothèque de décodage Aldes |

### 3. Transférez les Fichiers vers la carte

```bash
cd uAldes

# Copier tous les fichiers (utiliser :/ pour le répertoire racine)
mpremote fs cp main.py config.py espicoW.py simple_esp.py http_server.py ualdes.py :/

# Ou copier les fichiers un par un
mpremote fs cp main.py :/main.py
mpremote fs cp config.py :/config.py
mpremote fs cp espicoW.py :/espicoW.py
mpremote fs cp simple_esp.py :/simple_esp.py
mpremote fs cp http_server.py :/http_server.py
mpremote fs cp ualdes.py :/ualdes.py
```

### 4. Configurez le fichier `config.py`

Modifiez `config.py` avec vos paramètres avant de le transférer :

```python
# Services à activer
SERVICES = {
    "mqtt_enabled": False,  # True pour activer MQTT
    "http_enabled": True,   # True pour activer l'API HTTP
    "http_port": 80
}

WIFI_NETWORKS = {
    "ssid": "votre_ssid",
    "password": "votre_mot_de_passe"
}

# Configuration MQTT (uniquement si mqtt_enabled = True)
MQTT_CONFIG = {
    "broker": "adresse_broker",
    "port": 1883,
    "client_id": "aldes",
    "user": "utilisateur",
    "password": "mot_de_passe"
}

# Configuration matérielle
HARDWARE_CONFIG = {
    # ESP8285 (généralement pré-câblé sur UART0)
    "esp_uart_id": 0,
    "esp_tx_pin": 0,
    "esp_rx_pin": 1,

    # STM32 sur UART1
    "stm32_uart_id": 1,
    "stm32_tx_pin": 4,
    "stm32_rx_pin": 5,

    # LED (GPIO 25 par défaut)
    "led_pin": 25,
}
```

---

## Commandes mpremote utiles

```bash
# Lister les fichiers sur le Pico
mpremote fs ls

# Ouvrir un REPL (console interactive)
mpremote repl

# Exécuter un script sans le copier
mpremote run main.py

# Supprimer un fichier
mpremote fs rm :/fichier.py

# Reset le Pico
mpremote reset
```

---

## API HTTP

Lorsque `http_enabled` est activé dans `config.py`, une API REST est disponible sur le port configuré (80 par défaut).

### Endpoints disponibles

| Endpoint | Description | Exemple |
|----------|-------------|---------|
| `/status` | Dernières données reçues | `{"Etat": 1, "T_vmc": 20.5, ...}` |
| `/auto` | Passe en mode automatique | `{"status": "ok", "command": "auto"}` |
| `/boost` | Passe en mode boost | `{"status": "ok", "command": "boost"}` |
| `/confort?duration=N` | Mode confort (N jours) | `{"status": "ok", "command": "confort", "duration": 2}` |
| `/vacances?duration=N` | Mode vacances (N jours) | `{"status": "ok", "command": "vacances", "duration": 10}` |
| `/temp?value=N` | Règle la température | `{"status": "ok", "command": "temp", "temperature": 21.0}` |
| `/info` | Infos système (version, uptime, IP) | `{"version": "1.0", "uptime": "2h 30m", ...}` |
| `/help` | Documentation de l'API | Liste des endpoints |

### Exemples d'utilisation

```bash
# Récupérer le status
curl http://192.168.1.100/status

# Passer en mode auto
curl http://192.168.1.100/auto

# Passer en mode boost
curl http://192.168.1.100/boost

# Mode confort pour 3 jours
curl "http://192.168.1.100/confort?duration=3"

# Mode vacances pour 14 jours
curl "http://192.168.1.100/vacances?duration=14"

# Régler la température à 21°C
curl "http://192.168.1.100/temp?value=21"
```

---

## CLI (Interface en ligne de commande)

Un outil CLI interactif est disponible pour contrôler l'appareil depuis votre ordinateur.

### Installation

```bash
# Le CLI nécessite Python 3
python3 uAldes/ualdes_cli.py <IP_DU_PICO>
```

### Utilisation interactive

```bash
$ python3 ualdes_cli.py 192.168.1.79
Connected to 192.168.1.79
API: uAldes HTTP API v1.0
uAldes CLI - Type 'help' for available commands, 'quit' to exit
ualdes> status
+-------------------------------------+
|           STATUS ALDES              |
+-------------------------------------+
| Temperature VMC              21.0 °C |
| Temperature HP               45.5 °C |
| ...                                  |
+-------------------------------------+
ualdes> auto
Mode automatique active
ualdes> quit
```

### Commandes disponibles

| Commande | Description |
|----------|-------------|
| `status` | Affiche les données des capteurs |
| `auto` | Active le mode automatique |
| `boost` | Active le mode boost |
| `confort [N]` | Mode confort pour N jours |
| `vacances [N]` | Mode vacances pour N jours |
| `temp <valeur>` | Règle la température |
| `help` | Affiche l'aide |
| `quit` | Quitte le CLI |

### Options

```bash
# Exécuter une commande unique
python3 ualdes_cli.py 192.168.1.79 -c "status"

# Sortie JSON brute
python3 ualdes_cli.py 192.168.1.79 --json -c "status"
```

### Mode test

Ajoutez `--test` à n'importe quelle commande pour obtenir des données simulées sans envoyer de commande réelle :

```bash
ualdes> status --test
ualdes> auto --test
```

---

## Connexions Matérielles

```
Clone Pico W (RP2040+ESP8285)    STM32
┌─────────────────────┐          ┌─────────┐
│  GP4 (TX) ──────────┼─────────►│ RX      │
│  GP5 (RX) ◄─────────┼──────────│ TX      │
│  GND ───────────────┼──────────│ GND     │
└─────────────────────┘          └─────────┘
```

---

## Mise à jour du firmware ESP8285

Les anciens firmwares ESP8285 (AT v1.x de 2018) peuvent avoir des bugs réseau, notamment des problèmes ARP qui empêchent la communication. Si vous rencontrez des problèmes de connectivité (ping échoue, requêtes HTTP timeout), mettez à jour le firmware.

### Fichiers nécessaires

Les fichiers sont disponibles dans le dossier `firmware/`:
- `Serial_port_transmission.uf2` - Transforme le RP2040 en pont USB-série pour flasher l'ESP8285
- `espat_221_esp01s.bin` - Firmware AT v2.2.2.0-dev (Oct 2024) pour ESP8285

### Prérequis

```bash
# Installer esptool (avec pip dans un nix-shell)
nix-shell -p 'python3.withPackages (ps: [ ps.pip ps.pyserial ])' --run "pip install --target=/tmp/esptool_pkg esptool"
```

### Procédure de mise à jour

#### Étape 1: Flasher le pont série sur le RP2040

1. Déconnectez le câble USB
2. Maintenez le bouton **BOOTSEL** enfoncé
3. Connectez le câble USB tout en maintenant BOOTSEL
4. Relâchez le bouton - un lecteur **RPI-RP2** apparaît
5. Copiez le firmware:
   ```bash
   cp firmware/Serial_port_transmission.uf2 /run/media/$USER/RPI-RP2/
   ```

#### Étape 2: Mettre l'ESP8285 en mode flash

1. Déconnectez le câble USB
2. Maintenez le **deuxième bouton** enfoncé (pas BOOTSEL - souvent marqué "FLASH")
3. Connectez le câble USB tout en maintenant le bouton
4. Relâchez le bouton

#### Étape 3: Flasher le firmware ESP8285

```bash
nix-shell -p 'python3.withPackages (ps: [ ps.pip ps.pyserial ])' --run \
  "PYTHONPATH=/tmp/esptool_pkg python3 -m esptool -p /dev/ttyACM0 -b 115200 \
   write_flash -e -fm dout -ff 40m -fs 1MB 0 firmware/espat_221_esp01s.bin"
```

Sortie attendue:
```
Connecting....
Chip type:          ESP8285N08
Erasing flash memory...
Writing at 0x00100000... 100%
Hash of data verified.
```

#### Étape 4: Restaurer MicroPython sur le RP2040

1. Déconnectez le câble USB
2. Maintenez **BOOTSEL** enfoncé, connectez USB
3. Copiez le firmware MicroPython:
   ```bash
   cp RPI_PICO-20250911-v1.26.1.uf2 /run/media/$USER/RPI-RP2/
   ```

#### Étape 5: Vérifier la mise à jour

```bash
mpremote exec "
from machine import UART, Pin
import time
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
time.sleep(0.3)
while uart.any(): uart.read()
uart.write('AT+GMR\r\n')
time.sleep(0.5)
while uart.any(): print(uart.read().decode())
"
```

Résultat attendu: `AT version:2.2.2.0-dev`

---

## Optimisation des performances

### Réduire la latence réseau

Par défaut, l'ESP8285 utilise le mode "light-sleep" pour économiser l'énergie, ce qui augmente la latence (ping ~1000ms). Désactivez-le dans `config.py`:

```python
HARDWARE_CONFIG = {
    # ...
    "esp_sleep_mode": 0,  # 0 = désactivé (latence ~50ms), 1 = light-sleep (~1000ms)
}
```

---

## Dépannage

### ESP8285 ne répond pas
- Vérifiez que l'ESP8285 est bien connecté sur UART0 (GP0/GP1)
- Activez le mode debug: `"esp_debug": True`

### Pas de connexion WiFi
- Le réseau doit être en 2.4GHz (pas de support 5GHz)
- Vérifiez les identifiants

### Problèmes de connectivité réseau (ARP FAILED, ping timeout)
- Mettez à jour le firmware ESP8285 (voir section ci-dessus)
- Vérifiez la version avec `AT+GMR` - les versions < 2.x ont des bugs connus

### Erreur MQTT
- Vérifiez l'adresse et le port du broker
- SSL non supporté (utilisez le port 1883)

---

## Ressources supplémentaires

- [Documentation officielle MicroPython](https://micropython.org/)
- [Documentation mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html)
- [espicoW sur GitHub](https://github.com/asifneon13/espicoW)

---
