# STM32F411CEU6 USB-UART Bridge

Firmware pour la carte STM32F411CEU6 (Black Pill) qui crée un pont USB-UART :
- **USB CDC** : Port série virtuel sur USB
- **UART1** : Communication série sur PA9 (TX) / PA10 (RX) à 115200 bauds
- **LED PC13** : Clignote lors de l'activité

## Prérequis

### NixOS
```bash
# Toutes les dépendances sont gérées via nix-shell
```

### Autres distributions
```bash
# Installer le toolchain ARM
sudo apt install gcc-arm-none-eabi

# Installer dfu-util pour le flashage
sudo apt install dfu-util

# Installer pyserial pour les tests
pip install pyserial
```

## Compilation

```bash
cd Software/STM32F411CEU6

# Sur NixOS
nix-shell -p gcc-arm-embedded --run "make clean && make"

# Autres distributions
make clean && make
```

Le firmware compilé se trouve dans `build/blackpill_F411CEU6.bin`.

## Flash : DFU (via USB)

1. **Mettre la carte en mode DFU** :
   - Maintenir le bouton **BOOT0** enfoncé
   - Appuyer et relâcher le bouton **RESET**
   - Relâcher le bouton **BOOT0**

2. **Vérifier la détection** :
   ```bash
   lsusb | grep "0483:df11"
   # Doit afficher : STMicroelectronics STM Device in DFU Mode
   ```

3. **Flasher** :
   ```bash
   # Sur NixOS
   nix-shell -p gcc-arm-embedded dfu-util --run "make flash"

   # Autres distributions
   make flash
   ```

## Dépannage

### Périphérique non détecté

```bash
# Vérifier les périphériques USB
lsusb | grep 0483

# Vérifier les logs kernel
dmesg | tail -20

# Lister les ports série
ls -la /dev/ttyACM* /dev/ttyUSB*
```

### Permission refusée

```bash
# Ajouter l'utilisateur au groupe dialout
sudo usermod -a -G dialout $USER
# Se déconnecter et reconnecter

# Ou créer une règle udev
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/99-stm32.rules
sudo udevadm control --reload-rules
```

### Mode DFU non détecté

- Vérifier que BOOT0 est bien maintenu pendant le RESET
- Essayer un autre câble USB (vérifier que le câble USB supporte les données et
  pas uniquement l'alimentation)

## Structure du projet

```
Software/STM32F411CEU6/
├── src/                    # Code source
│   ├── main.c              # Point d'entrée et boucle principale
│   ├── main.h
│   ├── stm32f4xx_hal_msp.c # Configuration GPIO pour UART/USB
│   ├── stm32f4xx_it.c      # Gestionnaires d'interruptions
│   ├── system_stm32f4xx.c  # Initialisation système
│   ├── usb_device.c        # Initialisation USB
│   ├── usbd_cdc_if.c       # Interface USB CDC
│   ├── usbd_conf.c         # Configuration USB bas niveau
│   ├── usbd_desc.c         # Descripteurs USB
│   └── startup_stm32f411ceux.s
├── Inc/
│   └── stm32f4xx_hal_conf.h
├── Drivers/                # Bibliothèques HAL et CMSIS
├── Middlewares/            # USB Device Library
├── tests/                  # Scripts de test Python
├── build/                  # Fichiers compilés
├── Makefile
├── STM32F411CEUX_FLASH.ld  # Script de linkage
└── README.md
```
