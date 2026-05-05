# MediathekView Downloader

Ein macOS-Programm zum Herunterladen von Filmen und Serien von MediathekViewWeb.de.

## Funktionen

- **Suche**: Suchen Sie nach Titeln auf MediathekViewWeb.de
- **Qualität**: Automatisch höchste verfügbare Qualität (HD > SD > Low)
- **Filter**: Nur Inhalte ohne Audiodeskription
- **Download-Management**:
  - Fortschrittsanzeige
  - Pause/Fortsetzen/Abbrechen
- **Dateiverwaltung**:
  - Wählbares Ziellaufwerk
  - Serien: Ordner mit SxxExx-Benennung
  - Filme: Direkt im Hauptverzeichnis
- **Duplikat-Erkennung**: Warnung bei bereits vorhandenen Dateien

## Installation

1. Laden Sie den gesamten Code als ZIP herunter
2. Kopieren Sie `MediathekDownloader.app` aus 'dist' in den Ordner `/Applications`
3. Starten Sie die App aus dem Applications-Ordner

## Verwendung

1. Geben Sie einen Suchbegriff ein (z.B. "Tatort", "Polizeiruf")
2. Klicken Sie auf "Suchen"
3. Wählen Sie einen Eintrag aus und klicken Sie auf "Herunterladen"
4. Wählen Sie den Download-Ordner (Standard: ~/Downloads/MediathekView)
5. Der Download beginnt automatisch

## Anforderungen

- macOS 10.15 oder höher
- Internet-Verbindung für die MediathekViewWeb-Suche

## Technologie

- Python 3 + PyQt6
- yt-dlp für Downloads
- MediathekViewWeb API

## Lizenz

GNU GPL v3
