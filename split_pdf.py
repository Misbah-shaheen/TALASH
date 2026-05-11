import pdfplumber
from pypdf import PdfReader, PdfWriter
from pathlib import Path

input_pdf = "./cvs/Handler (8).pdf"
output_dir = "./cvs/split"
Path(output_dir).mkdir(exist_ok=True)

# Step 1: Extract ALL text with page numbers
print("Scanning pages...")
page_texts = []
with pdfplumber.open(input_pdf) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        page_texts.append((i, text))

# Step 2: Find candidate boundaries
# A new candidate starts when "Candidate for the Post of" appears
# This handles: new page, mid-page, after blank space — all cases
candidate_start_pages = []
for i, text in page_texts:
    if "Candidate for the Post of" in text:
        candidate_start_pages.append(i)
        print(f"  Candidate {len(candidate_start_pages)} starts at page {i}")

print(f"\nFound {len(candidate_start_pages)} candidates")

# Step 3: Split PDF at those boundaries
reader = PdfReader(input_pdf)
total_pages = len(reader.pages)

for idx, start_page in enumerate(candidate_start_pages, 1):
    end_page = candidate_start_pages[idx] if idx < len(candidate_start_pages) else total_pages

    writer = PdfWriter()
    for p in range(start_page, end_page):
        writer.add_page(reader.pages[p])

    out_path = f"{output_dir}/candidate_{idx:03d}.pdf"
    with open(out_path, "wb") as f:
        writer.write(f)
    print(f"  candidate_{idx:03d}.pdf → pages {start_page}–{end_page-1} ({end_page-start_page} pages)")

print(f"\n✅ Done! {len(candidate_start_pages)} PDFs in {output_dir}")