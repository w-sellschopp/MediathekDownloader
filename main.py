import sys
import os
import json
import requests
import threading
import time
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QFileDialog, QMessageBox, QHeaderView, QFrame,
    QDialog, QDialogButtonBox, QSplitter, QScrollArea, QGroupBox,
    QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction

API_URL = "https://mediathekviewweb.de/api/query"

class MediathekAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'de-DE,de;q=0.9',
            'Content-Type': 'application/json'
        })

    def search(self, query, max_results=100):
        try:
            queries_to_try = [
                [{'fields': ['title', 'topic', 'description'], 'query': query}],
                [{'fields': ['title', 'topic', 'description'], 'query': query.replace('die ', '').replace('Der ', '').replace('Das ', '')}],
            ]

            all_results = []
            seen_ids = set()

            for queries in queries_to_try:
                payload = {
                    'queries': queries,
                    'sortBy': 'timestamp',
                    'sortOrder': 'desc',
                    'size': max_results,
                    'future': False
                }
                response = self.session.post(API_URL, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_results(data)
                    for r in results:
                        if r['id'] not in seen_ids:
                            all_results.append(r)
                            seen_ids.add(r['id'])

            return all_results[:max_results]

        except Exception as e:
            print(f"API Error: {e}")
            return []

    def _parse_results(self, data):
        results = []
        try:
            items = data.get('result', {}).get('results', [])
        except (AttributeError, KeyError):
            items = []

        for item in items:
            result = {
                'id': item.get('id', ''),
                'title': item.get('title', ''),
                'topic': item.get('topic', ''),
                'channel': item.get('channel', ''),
                'timestamp': item.get('timestamp', 0),
                'duration': item.get('duration', 0),
                'description': item.get('description', ''),
                'url_video': item.get('url_video', ''),
                'url_video_low': item.get('url_video_low', ''),
                'url_video_hd': item.get('url_video_hd', ''),
                'url_subtitles': item.get('url_subtitle', ''),
                'filmliste_timestamp': item.get('filmlisteTimestamp', 0),
            }
            if result['title']:
                results.append(result)
        return results

class DownloadThread(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(int, str)
    error = pyqtSignal(int, str)
    status = pyqtSignal(int, str)

    def __init__(self, download_id, url, output_path, title, parent=None):
        super().__init__(parent)
        self.download_id = download_id
        self.url = url
        self.output_path = output_path
        self.title = title
        self._paused = False
        self._cancelled = False
        self._yt_dlp_opts = {}

    def run(self):
        try:
            import yt_dlp

            self.status.emit(self.download_id, "Starte Download...")

            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            self._yt_dlp_opts = {
                'outtmpl': self.output_path,
                'progress_hooks': [self._progress_hook],
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'http_chunk_size': 1048576,
            }

            with yt_dlp.YoutubeDL(self._yt_dlp_opts) as ydl:
                ydl.download([self.url])

            self.finished.emit(self.download_id, self.output_path)

        except Exception as e:
            self.error.emit(self.download_id, str(e))

    def _progress_hook(self, d):
        if self._cancelled:
            raise Exception("Download cancelled")

        while self._paused:
            time.sleep(0.1)
            if self._cancelled:
                raise Exception("Download cancelled")

        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = int((downloaded / total) * 100)
                self.progress.emit(self.download_id, percent)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True


class SearchThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query, api, parent=None):
        super().__init__(parent)
        self.query = query
        self.api = api

    def run(self):
        try:
            results = self.api.search(self.query)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ConfirmDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(message))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)


class MediathekDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = MediathekAPI()
        self.downloads = {}
        self.download_dir = str(Path.home() / "Downloads" / "MediathekView")

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MediathekView Downloader")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        toolbar = self._create_toolbar()
        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        search_group = self._create_search_group()
        splitter.addWidget(search_group)

        results_group = self._create_results_group()
        splitter.addWidget(results_group)

        downloads_group = self._create_downloads_group()
        splitter.addWidget(downloads_group)

        splitter.setSizes([100, 400, 200])
        main_layout.addWidget(splitter)

    def _create_toolbar(self):
        toolbar = QHBoxLayout()

        dir_label = QLabel("Download-Ordner:")
        toolbar.addWidget(dir_label)

        self.dir_label = QLabel(self.download_dir)
        self.dir_label.setStyleSheet("color: #0066cc; cursor: pointer;")
        self.dir_label.mousePressEvent = self._select_download_dir
        toolbar.addWidget(self.dir_label)

        toolbar.addStretch()

        return toolbar

    def _create_search_group(self):
        group = QGroupBox("Suche")
        layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Titel eingeben (z.B. Tatort, Polizeiruf)")
        self.search_input.returnPressed.connect(self._perform_search)
        layout.addWidget(self.search_input)

        search_btn = QPushButton("Suchen")
        search_btn.clicked.connect(self._perform_search)
        layout.addWidget(search_btn)

        self.search_status = QLabel("")
        layout.addWidget(self.search_status)

        group.setLayout(layout)
        return group

    def _create_results_group(self):
        group = QGroupBox("Suchergebnisse")
        layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Titel", "Thema", "Sender", "Dauer", "Datum", "AD", "Download"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.results_table)
        group.setLayout(layout)
        return group

    def _create_downloads_group(self):
        group = QGroupBox("Aktive Downloads")
        layout = QVBoxLayout()

        self.downloads_table = QTableWidget()
        self.downloads_table.setColumnCount(5)
        self.downloads_table.setHorizontalHeaderLabels([
            "Titel", "Fortschritt", "Status", "Größe", "Aktionen"
        ])
        self.downloads_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.downloads_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.downloads_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.downloads_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.downloads_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.downloads_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.downloads_table.setRowCount(0)

        layout.addWidget(self.downloads_table)
        group.setLayout(layout)
        return group

    def _select_download_dir(self, event):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Download-Ordner wählen", self.download_dir
        )
        if dir_path:
            self.download_dir = dir_path
            self.dir_label.setText(self.download_dir)

    def _perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self.search_status.setText("Suche läuft...")
        self.results_table.setRowCount(0)

        self.search_thread = SearchThread(query, self.api)
        self.search_thread.finished.connect(self._on_search_finished)
        self.search_thread.error.connect(self._on_search_error)
        self.search_thread.start()

    def _on_search_finished(self, results):
        filtered_results = []
        for r in results:
            title = r.get('title', '')
            title_lower = title.lower()
            desc_lower = r.get('description', '').lower()

            has_ad = (
                'audiodeskription' in title_lower or
                '(ad)' in title_lower or
                'audio-description' in title_lower or
                'audiodeskription' in desc_lower or
                'audio-description' in desc_lower
            )
            r['has_audio_desc'] = has_ad
            r['title_original'] = title

            if not has_ad:
                filtered_results.append(r)

        self.search_status.setText(f"{len(filtered_results)} Ergebnisse (ohne AD)")
        self.search_results = self._sort_results(filtered_results)
        self._display_results(self.search_results)

    def _on_search_error(self, error):
        self.search_status.setText(f"Fehler: {error}")
        QMessageBox.warning(self, "Suchfehler", error)

    def _sort_results(self, results):
        import re

        def get_episode_number(title):
            season = 1
            episode = 0

            match = re.search(r'S(\d{1,2})\s*[/E]?\s*E(\d{1,2})', title, re.IGNORECASE)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
            else:
                match = re.search(r'S(\d{1,2})', title, re.IGNORECASE)
                if match:
                    season = int(match.group(1))
                    match2 = re.search(r'E(\d{1,2})', title, re.IGNORECASE)
                    if match2:
                        episode = int(match2.group(1))

            if episode == 0:
                match = re.search(r'\((\d+)/(\d+)\)', title)
                if match:
                    episode = int(match.group(1))

            if episode == 0:
                match = re.search(r'Folge\s*(\d{1,2})', title, re.IGNORECASE)
                if match:
                    episode = int(match.group(1))

            return (season, episode)

        def get_sort_key(r):
            topic = r.get('topic', '')
            title = r.get('title', '')
            season, episode = get_episode_number(title)
            return (topic, season, episode)

        return sorted(results, key=get_sort_key)

    def _display_results(self, results):
        self.results_table.setRowCount(0)

        for i, result in enumerate(results):
            self.results_table.insertRow(i)

            title_item = QTableWidgetItem(result.get('title', ''))
            title_item.setData(Qt.ItemDataRole.UserRole, result)
            self.results_table.setItem(i, 0, title_item)
            self.results_table.setItem(i, 1, QTableWidgetItem(result.get('topic', '')))
            self.results_table.setItem(i, 2, QTableWidgetItem(result.get('channel', '')))

            duration = result.get('duration', 0)
            minutes = duration // 60 if duration else 0
            self.results_table.setItem(i, 3, QTableWidgetItem(f"{minutes} min"))

            timestamp = result.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    date_str = dt.strftime("%d.%m.%Y")
                except:
                    date_str = ""
            else:
                date_str = ""
            self.results_table.setItem(i, 4, QTableWidgetItem(date_str))

            ad_text = "Ja" if result.get('has_audio_desc', False) else "Nein"
            self.results_table.setItem(i, 5, QTableWidgetItem(ad_text))

            download_btn = QPushButton("Herunterladen")
            download_btn.clicked.connect(lambda checked, r=result: self._start_download(r))
            self.results_table.setCellWidget(i, 6, download_btn)

    def _get_best_url(self, result):
        if result.get('url_video_hd'):
            return result['url_video_hd']
        if result.get('url_video'):
            return result['url_video']
        if result.get('url_video_low'):
            return result['url_video_low']
        return None

    def _get_output_path(self, result):
        title = result.get('title', 'download')
        topic = result.get('topic', '')

        is_series = bool(topic and topic != title)

        if is_series:
            series_folder = self._sanitize_filename(topic)
            series_path = os.path.join(self.download_dir, series_folder)

            season, episode = self._extract_episode_number(title)
            if season > 0 and episode > 0:
                filename = f"S{season:02d}E{episode:02d}.mp4"
            else:
                filename = f"{self._sanitize_filename(title)}.mp4"

            return os.path.join(series_path, filename)
        else:
            filename = self._sanitize_filename(title)
            return os.path.join(self.download_dir, f"{filename}.mp4")

    def _sanitize_filename(self, name):
        import re
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = name[:200]
        return name

    def _extract_episode_number(self, title):
        import re
        season = 0
        episode = 0

        match = re.search(r'S(\d{1,2})\s*[/E]?\s*E(\d{1,2})', title, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return (season, episode)

        match = re.search(r'S(\d{1,2})', title, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            match2 = re.search(r'E(\d{1,2})', title, re.IGNORECASE)
            if match2:
                episode = int(match2.group(1))
            return (season, episode)

        match = re.search(r'\((\d+)/(\d+)\)', title)
        if match:
            episode = int(match.group(1))
            season = 1
            return (season, episode)

        match = re.search(r'Folge\s*(\d{1,2})', title, re.IGNORECASE)
        if match:
            episode = int(match.group(1))
            season = 1

        return (season, episode)

    def _check_existing_file(self, filepath):
        return os.path.exists(filepath)

    def _start_download(self, result):
        url = self._get_best_url(result)
        if not url:
            QMessageBox.warning(self, "Kein Download-Link",
                "Für diesen Eintrag ist kein Download-Link verfügbar.")
            return

        output_path = self._get_output_path(result)

        if self._check_existing_file(output_path):
            response = QMessageBox.question(
                self, "Datei existiert bereits",
                f"Die Datei\n{output_path}\n Existiert bereits. Möchten Sie sie überschreiben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if response == QMessageBox.StandardButton.No:
                return

        download_id = len(self.downloads)

        self.downloads[download_id] = {
            'result': result,
            'url': url,
            'output_path': output_path,
            'thread': None,
            'progress': 0,
            'status': 'Wartend',
            'paused': False
        }

        self._add_download_row(download_id, result.get('title', ''))

        thread = DownloadThread(download_id, url, output_path, result.get('title', ''))
        thread.progress.connect(self._on_download_progress)
        thread.finished.connect(self._on_download_finished)
        thread.error.connect(self._on_download_error)
        thread.status.connect(self._on_download_status)

        self.downloads[download_id]['thread'] = thread
        thread.start()

    def _add_download_row(self, download_id, title):
        row = self.downloads_table.rowCount()
        self.downloads_table.insertRow(row)

        title_item = QTableWidgetItem(title)
        self.downloads_table.setItem(row, 0, title_item)

        progress_bar = QProgressBar()
        progress_bar.setValue(0)
        self.downloads_table.setCellWidget(row, 1, progress_bar)

        status_item = QTableWidgetItem("Wartend")
        self.downloads_table.setItem(row, 2, status_item)

        size_item = QTableWidgetItem("0 MB")
        self.downloads_table.setItem(row, 3, size_item)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(2, 2, 2, 2)

        pause_btn = QPushButton("⏸")
        pause_btn.setFixedWidth(40)
        pause_btn.clicked.connect(lambda: self._toggle_pause(download_id))
        buttons_layout.addWidget(pause_btn)

        cancel_btn = QPushButton("✕")
        cancel_btn.setFixedWidth(40)
        cancel_btn.clicked.connect(lambda: self._cancel_download(download_id))
        buttons_layout.addWidget(cancel_btn)

        container = QWidget()
        container.setLayout(buttons_layout)
        self.downloads_table.setCellWidget(row, 4, container)

        self.downloads[download_id]['row'] = row
        self.downloads[download_id]['progress_bar'] = progress_bar
        self.downloads[download_id]['size_item'] = size_item

    def _on_download_progress(self, download_id, percent):
        if download_id in self.downloads:
            info = self.downloads[download_id]
            info['progress'] = percent
            if 'progress_bar' in info:
                info['progress_bar'].setValue(percent)

            status_item = self.downloads_table.item(info.get('row', 0), 2)
            if status_item:
                status_item.setText(f"{percent}%")

    def _on_download_status(self, download_id, status):
        if download_id in self.downloads:
            info = self.downloads[download_id]
            info['status'] = status
            row = info.get('row', 0)
            status_item = self.downloads_table.item(row, 2)
            if status_item:
                status_item.setText(status)

    def _on_download_finished(self, download_id, output_path):
        if download_id in self.downloads:
            info = self.downloads[download_id]
            row = info.get('row', 0)

            status_item = self.downloads_table.item(row, 2)
            if status_item:
                status_item.setText("Abgeschlossen")

            if 'progress_bar' in info:
                info['progress_bar'].setValue(100)

            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            size_mb = file_size / (1024 * 1024)
            size_item = self.downloads_table.item(row, 3)
            if size_item:
                size_item.setText(f"{size_mb:.1f} MB")

            status_item = self.downloads_table.item(row, 2)
            if status_item:
                status_item.setText("Abgeschlossen")

            del self.downloads[download_id]

    def _on_download_error(self, download_id, error):
        if download_id in self.downloads:
            info = self.downloads[download_id]
            row = info.get('row', 0)

            status_item = self.downloads_table.item(row, 2)
            if status_item:
                status_item.setText(f"Fehler: {error}")

            QMessageBox.warning(self, "Download-Fehler", error)

    def _toggle_pause(self, download_id):
        if download_id in self.downloads:
            info = self.downloads[download_id]
            thread = info.get('thread')

            if thread:
                if info.get('paused', False):
                    thread.resume()
                    info['paused'] = False
                    row = info.get('row', 0)
                    status_item = self.downloads_table.item(row, 2)
                    if status_item:
                        status_item.setText("Wird heruntergeladen...")
                else:
                    thread.pause()
                    info['paused'] = True
                    row = info.get('row', 0)
                    status_item = self.downloads_table.item(row, 2)
                    if status_item:
                        status_item.setText("Pausiert")

    def _cancel_download(self, download_id):
        if download_id in self.downloads:
            info = self.downloads[download_id]
            thread = info.get('thread')

            if thread:
                thread.cancel()

            row = info.get('row', 0)
            self.downloads_table.removeRow(row)

            del self.downloads[download_id]


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MediathekDownloader()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()