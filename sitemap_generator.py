import os
import sys
import json
import time
import urllib.request
import urllib.parse
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser
import threading
import collections
import xml.etree.ElementTree as ET
import http.server
import socketserver
import webbrowser
import subprocess
import socket

# Static asset extensions to ignore during crawl
IGNORED_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff',
    '.css', '.js', '.map',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.rar', '.tar', '.gz', '.7z',
    '.mp4', '.webm', '.ogg', '.mp3', '.wav',
    '.xml', '.json', '.txt', '.rss', '.atom',
    '.woff', '.woff2', '.ttf', '.eot', '.otf'
}

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value:
                    self.links.append(value.strip())

class SitemapCrawler:
    def __init__(self, start_url, max_urls=5000, delay=0.1, concurrency=3, ignore_query=True, output_dir=None):
        self.start_url = self.normalize_start_url(start_url)
        self.parsed_start = urlparse(self.start_url)
        self.target_domain = self.parsed_start.netloc
        self.max_urls = max_urls
        self.delay = delay
        self.concurrency = concurrency
        self.ignore_query = ignore_query
        self.output_dir = output_dir or os.path.dirname(os.path.abspath(__file__))
        
        # Crawler State
        self.visited = set()
        self.queue = collections.deque([self.start_url])
        self.sitemap_urls = []  # List of URLs that returned 200 OK
        self.errors = {}        # URL -> error message
        self.active_workers = 0
        self.running = False
        self.paused = False
        
        # Threading
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.threads = []
        
        # Statistics
        self.start_time = None
        self.end_time = None
        self.total_pages_fetched = 0
        self.current_action = "Idle"

    def normalize_start_url(self, url):
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        if not parsed.path:
            url = url + '/'
        return url

    def is_same_domain(self, url):
        parsed = urlparse(url)
        # Match domain and its subdomains (e.g. www.miamai.it and miamai.it)
        domain1 = parsed.netloc.lower()
        domain2 = self.target_domain.lower()
        if domain1 == domain2:
            return True
        if domain1.endswith('.' + domain2) or domain2.endswith('.' + domain1):
            return True
        return False

    def should_ignore(self, url):
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check extensions
        _, ext = os.path.splitext(path)
        if ext in IGNORED_EXTENSIONS:
            return True
            
        # Basic filter for common dynamic actions
        if any(p in path for p in ['/cdn-cgi/', '/wp-admin/', '/checkout/', '/cart/', '/my-account/', '/logout/']):
            return True
            
        return False

    def clean_url(self, base_url, href):
        # Resolve relative URL
        resolved = urljoin(base_url, href)
        parsed = urlparse(resolved)
        
        # Strip fragment
        if self.ignore_query:
            clean = parsed._replace(query="", fragment="").geturl()
        else:
            clean = parsed._replace(fragment="").geturl()
            
        return clean

    def fetch_page(self, url):
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 SitemapGenerator/1.0'}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('text/html'):
                    return 200, None, f"Skipped (Non-HTML: {content_type})"
                
                html_bytes = response.read()
                charset = response.headers.get_content_charset() or 'utf-8'
                try:
                    html_text = html_bytes.decode(charset, errors='replace')
                except Exception:
                    html_text = html_bytes.decode('utf-8', errors='replace')
                    
                return response.getcode(), html_text, None
        except urllib.error.HTTPError as e:
            return e.code, None, str(e)
        except Exception as e:
            return 0, None, str(e)

    def worker(self):
        while True:
            url = None
            with self.lock:
                while self.running and not self.paused and len(self.queue) == 0 and self.active_workers > 0:
                    self.condition.wait(timeout=0.5)
                
                if not self.running or (len(self.queue) == 0 and self.active_workers == 0) or self.paused:
                    break
                
                if len(self.queue) > 0:
                    url = self.queue.popleft()
                    self.visited.add(url)
                    self.active_workers += 1
                else:
                    continue

            if not url:
                continue

            # Process URL
            self.log_info(f"Crawling: {url}")
            status, html_content, err_msg = self.fetch_page(url)
            
            new_links = []
            if status == 200:
                with self.lock:
                    if url not in self.sitemap_urls:
                        self.sitemap_urls.append(url)
                
                if html_content:
                    parser = LinkParser()
                    try:
                        parser.feed(html_content)
                        new_links = parser.links
                    except Exception as pe:
                        self.log_info(f"Parser error for {url}: {pe}")
            else:
                with self.lock:
                    self.errors[url] = f"Status {status} - {err_msg}"
                self.log_info(f"Failed ({status}): {url} - {err_msg}")

            # Process discovered links
            added_count = 0
            with self.lock:
                self.total_pages_fetched += 1
                self.active_workers -= 1
                
                if status == 200 and html_content:
                    for link in new_links:
                        cleaned = self.clean_url(url, link)
                        if self.is_same_domain(cleaned) and not self.should_ignore(cleaned):
                            if cleaned not in self.visited and cleaned not in self.queue:
                                self.queue.append(cleaned)
                                added_count += 1
                
                # Notify other threads that work is available or that we finished
                self.condition.notify_all()

            # Rate limit delay
            if self.delay > 0:
                time.sleep(self.delay)

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.paused = False
            self.start_time = time.time()
            self.current_action = "Crawling"
            self.total_pages_fetched = 0
            self.sitemap_urls = []
            self.errors = {}
            # Reset queue if empty but starting new
            if not self.queue:
                self.queue.append(self.start_url)
                self.visited.clear()
            self.log_info(f"Starting crawl for {self.start_url} (Max threads: {self.concurrency}, Delay: {self.delay}s)")
            
        # Spawn workers
        for i in range(self.concurrency):
            t = threading.Thread(target=self.worker, name=f"CrawlerWorker-{i}")
            t.daemon = True
            t.start()
            self.threads.append(t)
            
        # Spawn manager thread to monitor completion
        m = threading.Thread(target=self.monitor, name="CrawlerMonitor")
        m.daemon = True
        m.start()

    def stop(self):
        with self.lock:
            self.running = False
            self.current_action = "Stopped"
            self.condition.notify_all()
        self.log_info("Crawl execution stopped by user.")

    def monitor(self):
        for t in self.threads:
            t.join()
            
        with self.lock:
            self.running = False
            self.end_time = time.time()
            self.current_action = "Generating Sitemaps"
            
        self.log_info(f"Crawl completed. Discovered {len(self.sitemap_urls)} pages with 200 OK. Writing sitemaps...")
        self.generate_sitemap_files()
        
        with self.lock:
            self.current_action = "Completed"
            
        self.log_info(f"All sitemaps successfully generated in: {self.output_dir}")

    def generate_sitemap_files(self):
        # Create output dir if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Clean existing sitemap files in output_dir to avoid confusion
        for filename in os.listdir(self.output_dir):
            if filename.startswith("sitemap") and filename.endswith(".xml"):
                try:
                    os.remove(os.path.join(self.output_dir, filename))
                except Exception:
                    pass
        
        urls = sorted(list(set(self.sitemap_urls)))
        if not urls:
            # Create a single empty sitemap or at least the start_url
            urls = [self.start_url]
            
        # Helper to format dates
        today = time.strftime("%Y-%m-%d")
        
        # Chunk URLs based on max_urls limit
        chunks = [urls[i:i + self.max_urls] for i in range(0, len(urls), self.max_urls)]
        
        sitemap_filenames = []
        
        if len(chunks) <= 1:
            # Write a single sitemap.xml
            filepath = os.path.join(self.output_dir, "sitemap.xml")
            self.write_sitemap_chunk(filepath, urls, today)
            sitemap_filenames.append("sitemap.xml")
        else:
            # Write multiple sitemaps sitemap_1.xml, sitemap_2.xml, etc.
            for idx, chunk in enumerate(chunks, 1):
                filename = f"sitemap_{idx}.xml"
                filepath = os.path.join(self.output_dir, filename)
                self.write_sitemap_chunk(filepath, chunk, today)
                sitemap_filenames.append(filename)
                
            # Write sitemap index file sitemap.xml
            self.write_sitemap_index(os.path.join(self.output_dir, "sitemap.xml"), sitemap_filenames, today)
            sitemap_filenames.insert(0, "sitemap.xml")
            
        self.generated_files = sitemap_filenames

    def write_sitemap_chunk(self, filepath, urls, date_str):
        root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        
        for url in urls:
            url_el = ET.SubElement(root, "url")
            loc_el = ET.SubElement(url_el, "loc")
            loc_el.text = url
            
            lastmod_el = ET.SubElement(url_el, "lastmod")
            lastmod_el.text = date_str
            
            changefreq_el = ET.SubElement(url_el, "changefreq")
            # Set home page priority higher
            parsed = urlparse(url)
            if parsed.path == "/" or not parsed.path:
                changefreq_el.text = "daily"
                priority_el = ET.SubElement(url_el, "priority")
                priority_el.text = "1.0"
            else:
                changefreq_el.text = "weekly"
                priority_el = ET.SubElement(url_el, "priority")
                priority_el.text = "0.7"
                
        # Generate pretty XML
        xml_str = ET.tostring(root, encoding='utf-8')
        # Simple indentation for readability
        from xml.dom import minidom
        reparsed = minidom.parseString(xml_str)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding="utf-8")
        
        with open(filepath, 'wb') as f:
            f.write(pretty_xml)

    def write_sitemap_index(self, filepath, sitemap_files, date_str):
        root = ET.Element("sitemapindex", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        
        # Build base URL for the sitemap files (must refer to the website where they are uploaded)
        # e.g., if target is https://miamai.it/ and file is sitemap_1.xml, loc will be https://miamai.it/sitemap_1.xml
        base_sitemap_url = self.start_url
        if not base_sitemap_url.endswith('/'):
            base_sitemap_url += '/'
            
        for sfile in sitemap_files:
            sitemap_el = ET.SubElement(root, "sitemap")
            loc_el = ET.SubElement(sitemap_el, "loc")
            loc_el.text = urljoin(base_sitemap_url, sfile)
            
            lastmod_el = ET.SubElement(sitemap_el, "lastmod")
            lastmod_el.text = date_str
            
        xml_str = ET.tostring(root, encoding='utf-8')
        from xml.dom import minidom
        reparsed = minidom.parseString(xml_str)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding="utf-8")
        
        with open(filepath, 'wb') as f:
            f.write(pretty_xml)

    def log_info(self, message):
        timestamp = time.strftime("[%H:%M:%S]")
        print(f"{timestamp} {message}")
        # We will write to a memory log or output for UI polling
        global app_logs
        with logs_lock:
            app_logs.append(f"{timestamp} {message}")
            if len(app_logs) > 500:
                app_logs.pop(0)

    def get_status_dict(self):
        with self.lock:
            elapsed = 0
            if self.start_time:
                end = self.end_time or time.time()
                elapsed = round(end - self.start_time, 1)
                
            return {
                "running": self.running,
                "current_action": self.current_action,
                "pages_fetched": self.total_pages_fetched,
                "discovered_urls": len(self.sitemap_urls),
                "queue_size": len(self.queue),
                "errors_count": len(self.errors),
                "elapsed_seconds": elapsed,
                "generated_files": getattr(self, "generated_files", []),
                "output_dir": self.output_dir
            }

# Shared Application State
crawler_instance = None
app_logs = []
logs_lock = threading.Lock()

class SitemapServerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress request logging to avoid terminal spam
        pass

    def do_GET(self):
        global crawler_instance, app_logs
        
        # API Endpoints
        if self.path == '/api/status':
            status = crawler_instance.get_status_dict() if crawler_instance else {
                "running": False,
                "current_action": "Idle",
                "pages_fetched": 0,
                "discovered_urls": 0,
                "queue_size": 0,
                "errors_count": 0,
                "elapsed_seconds": 0,
                "generated_files": [],
                "output_dir": ""
            }
            
            with logs_lock:
                status["logs"] = list(app_logs)
                
            self.send_json(status)
            return
            
        # Serve static files from ui/ directory
        clean_path = self.path.split('?')[0].split('#')[0]
        if clean_path == '/':
            clean_path = '/index.html'
            
        # Root of workspace
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'ui', clean_path.lstrip('/'))
        
        if os.path.isfile(file_path):
            self.send_response(200)
            # Determine content type
            if file_path.endswith('.html'):
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            elif file_path.endswith('.css'):
                self.send_header('Content-Type', 'text/css; charset=utf-8')
            elif file_path.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            elif file_path.endswith('.json'):
                self.send_header('Content-Type', 'application/json; charset=utf-8')
            else:
                self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        global crawler_instance, app_logs
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        params = {}
        if post_data:
            try:
                params = json.loads(post_data.decode('utf-8'))
            except Exception:
                pass
                
        if self.path == '/api/start':
            # Stop existing run if any
            if crawler_instance and crawler_instance.running:
                crawler_instance.stop()
                
            url = params.get('url', 'https://miamai.it')
            limit = int(params.get('limit', 5000))
            delay = float(params.get('delay', 0.1))
            concurrency = int(params.get('concurrency', 3))
            ignore_query = bool(params.get('ignore_query', True))
            output_dir = params.get('output_dir', '').strip()
            
            if not output_dir:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(current_dir, 'sitemaps')
                
            with logs_lock:
                app_logs.clear()
                
            crawler_instance = SitemapCrawler(
                start_url=url,
                max_urls=limit,
                delay=delay,
                concurrency=concurrency,
                ignore_query=ignore_query,
                output_dir=output_dir
            )
            crawler_instance.start()
            self.send_json({"status": "started"})
            return
            
        elif self.path == '/api/stop':
            if crawler_instance:
                crawler_instance.stop()
            self.send_json({"status": "stopping"})
            return
            
        elif self.path == '/api/open-folder':
            folder = params.get('folder', '')
            if folder and os.path.isdir(folder):
                try:
                    if sys.platform == 'win32':
                        os.startfile(folder)
                    elif sys.platform == 'darwin':
                        subprocess.Popen(['open', folder])
                    else:
                        subprocess.Popen(['xdg-open', folder])
                    self.send_json({"success": True})
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)})
            else:
                self.send_json({"success": False, "error": "Folder does not exist"})
            return
            
        self.send_error(404, "Endpoint not found")

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

class ReuseAddrThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTPServer with SO_REUSEADDR.
    
    ThreadingMixIn makes each request run in its own thread so concurrent
    API polling from the browser never blocks the crawler or other requests.
    """
    allow_reuse_address = True
    daemon_threads = True  # Threads die when main process exits


def run_server():
    port = 8000
    while port < 8020:
        try:
            server = ReuseAddrThreadingHTTPServer(('localhost', port), SitemapServerHandler)
            print(f"[OK] Server avviato su http://localhost:{port}")
            print(f"[  ] Il browser si apre automaticamente...")
            # Open browser with a short delay so the socket is fully bound first
            threading.Timer(0.8, webbrowser.open, args=[f"http://localhost:{port}"]).start()
            server.serve_forever()
            break
        except OSError as e:
            print(f"[!] Porta {port} occupata ({e}), provo la {port+1}...")
            port += 1
    else:
        print("[ERRORE] Nessuna porta disponibile tra 8000-8019. Chiudi altri programmi e riprova.")
        input("Premi INVIO per uscire...")


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 50)
    print("  Google Sitemap Generator Pro - miamai.it")
    print("=" * 50)
    run_server()
