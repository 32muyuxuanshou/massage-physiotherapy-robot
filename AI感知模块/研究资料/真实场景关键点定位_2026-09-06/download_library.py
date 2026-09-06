"""Download public paper PDFs to the ignored local library; never fetch model weights.
Run with a Python environment providing requests, beautifulsoup4 and pypdf.
"""
import concurrent.futures, hashlib, json, pathlib, subprocess
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
ROOT = pathlib.Path(__file__).resolve().parent
catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
def fetch(p):
    result = {"id":p["id"],"key":p["key"],"source":p["source"]}
    dest = ROOT / "local/pdfs" / (p["id"]+"_"+p["key"]+".pdf")
    try:
        if not dest.exists():
            if not p.get("pdf_url"):
                raise ValueError("No verified public PDF endpoint; see source landing page")
            r = requests.get(p["pdf_url"], timeout=60)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF-"):
                raise ValueError("Endpoint did not return PDF")
            dest.write_bytes(r.content)
        reader = PdfReader(dest)
        result.update(pdf=str(dest.relative_to(ROOT)).replace("\\","/"),bytes=dest.stat().st_size,
                      sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),pages=len(reader.pages),download_status="available")
        result["pdf_metadata"] = {str(k):str(v) for k,v in (reader.metadata or {}).items() if k in ["/Title","/Author"]}
        txt=ROOT/"local/text"/(p["id"]+"_"+p["key"]+".txt")
        proc=subprocess.run(["pdftotext","-layout",str(dest),str(txt)],capture_output=True)
        result["extract_status"]="ok" if proc.returncode==0 else "failed"
        result["parser_warnings"]=proc.stderr.decode("utf-8",errors="replace")[:1200]
        if p["arxiv"]:
            meta=requests.get(p["source"],timeout=25)
            if meta.ok:
                soup=BeautifulSoup(meta.text,"html.parser")
                result["verified_metadata"]={k:[m.get("content","") for m in soup.select('meta[name="'+k+'"]')] for k in ["citation_title","citation_author","citation_date","citation_arxiv_id"]}
        print(p["id"],result["download_status"],result["pages"],flush=True)
    except Exception as exc:
        result["download_status"]="failed"
        result["error"]=str(exc)
        print(p["id"],"FAILED",str(exc)[:120],flush=True)
    return result
if __name__=="__main__":
    (ROOT/"local/pdfs").mkdir(parents=True,exist_ok=True)
    (ROOT/"local/text").mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,catalog["papers"]))
    (ROOT/"download_manifest.json").write_text(json.dumps({"date":"2026-09-06","papers":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
