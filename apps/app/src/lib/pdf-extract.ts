/**
 * Client-side PDF text extraction using pdfjs-dist.
 *
 * Uses worker served from /public/pdf.worker.min.mjs.
 */

type PdfExtractResult = {
  text: string;
  pageCount: number;
  charCount: number;
};

let workerConfigured = false;

async function getPdfJs() {
  const pdfjs = await import("pdfjs-dist");

  if (!workerConfigured) {
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
    workerConfigured = true;
  }

  return pdfjs;
}

export async function extractTextFromPdf(file: File): Promise<PdfExtractResult> {
  const pdfjs = await getPdfJs();
  const data = new Uint8Array(await file.arrayBuffer());

  const loadingTask = pdfjs.getDocument({ data });
  const pdf = await loadingTask.promise;

  const pageTexts: string[] = [];

  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
    const page = await pdf.getPage(pageNum);
    const textContent = await page.getTextContent();
    const pageText = (textContent.items as Array<{ str?: string }>)
      .map((item) => item.str ?? "")
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();

    if (pageText) {
      pageTexts.push(pageText);
    }
  }

  const text = pageTexts.join("\n\n");

  return {
    text,
    pageCount: pdf.numPages,
    charCount: text.length,
  };
}

