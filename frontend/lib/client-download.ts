export function downloadTextFile(filename: string, content: string, type = "text/csv;charset=utf-8") {
  const objectUrl = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

export function csvRow(values: Array<string | number>) {
  return values.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",");
}
