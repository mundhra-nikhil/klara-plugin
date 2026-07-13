import {
  searchRobust,
  searchWithVariations,
  isNormalizedMatch,
  generateSearchVariations,
} from "./utils";

export async function getDocumentMetadata(): Promise<{ title: string; author: string }> {
  try {
    let title = "";
    let author = "";
    await Word.run(async (context) => {
      const props = context.document.properties;
      context.load(props, "title");
      await context.sync();
      title = props.title || "";
    }).catch(() => {});

    try {
      await Word.run(async (context) => {
        const authorProp = (context.document as any).getCustomProperties?.() || null;
        if (authorProp) {
          context.load(authorProp, "items");
          await context.sync();
          const authorItem = authorProp.tryGetByKey("Author");
          if (authorItem && !authorItem.isNull) {
            author = authorItem.value?.toString() || "";
          }
        }
      }).catch(() => {});
    } catch {
      // ignore custom property errors
    }

    return { title, author };
  } catch {
    return { title: "", author: "" };
  }
}

export async function getDocumentSelection(): Promise<string> {
  try {
    let text = "";
    await Word.run(async (context) => {
      const selection = context.document.getSelection();
      context.load(selection, "text");
      await context.sync();
      text = selection.text || "";
    }).catch(() => {});
    return text;
  } catch {
    return "";
  }
}

export async function getActiveDocumentData(): Promise<{
  title: string;
  author: string;
  url?: string;
  blob?: Blob;
}> {
  let title = "Document.docx";
  let author = "Unknown";
  let url = Office.context.document.url;

  try {
    await Word.run(async (context) => {
      const props = context.document.properties;
      context.load(props, "title, author");
      await context.sync();
      if (props.title) title = props.title;
      if ((props as any).author) author = (props as any).author;
    });
  } catch (e) {
    // ignore
  }

  // NOTE: Even when the document is cloud-hosted (url is an https:// SharePoint/OneDrive link)
  // we still extract the binary via getFileAsync, because the backend does not yet have a
  // Graph-URL ingestion endpoint. Once that endpoint is built, we can return { title, author, url }
  // here for the faster server-side pull path.

  // Fallback to getFileAsync for local/unsaved docs
  return new Promise((resolve, reject) => {
    Office.context.document.getFileAsync(
      Office.FileType.Compressed,
      { sliceSize: 65536 },
      (result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          const file = result.value;
          const sliceCount = file.sliceCount;
          const slicesReceived: ArrayBuffer[] = [];
          let slicesRead = 0;

          const getSlice = (sliceIndex: number) => {
            file.getSliceAsync(sliceIndex, (sliceResult) => {
              if (sliceResult.status === Office.AsyncResultStatus.Succeeded) {
                // Ensure the slice data is Uint8Array
                const sliceData = sliceResult.value.data;
                let typedArray: Uint8Array;
                if (sliceData instanceof ArrayBuffer) {
                  typedArray = new Uint8Array(sliceData);
                } else if (sliceData instanceof Uint8Array) {
                  typedArray = sliceData;
                } else {
                  typedArray = new Uint8Array(sliceData as any);
                }
                slicesReceived[sliceIndex] = typedArray.buffer as ArrayBuffer;
                slicesRead++;

                if (slicesRead === sliceCount) {
                  file.closeAsync();
                  const blob = new Blob(slicesReceived, {
                    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  });
                  resolve({ title, author, blob });
                } else {
                  getSlice(sliceIndex + 1);
                }
              } else {
                file.closeAsync();
                reject(new Error(sliceResult.error.message));
              }
            });
          };

          if (sliceCount > 0) {
            getSlice(0);
          } else {
            file.closeAsync();
            resolve({ title, author, blob: new Blob() });
          }
        } else {
          reject(new Error(result.error.message));
        }
      }
    );
  });
}

/**
 * Test if Word API is available and working properly
 * Returns true if Word API is responsive, false otherwise
 */
export async function testWordApiAvailability(): Promise<{
  available: boolean;
  error?: string;
  documentInfo?: any;
}> {
  try {
    let documentInfo: any = {};

    await Word.run(async (context) => {
      try {
        const doc = context.document;
        const body = doc.body;

        // Test basic document access
        context.load(body, "text");
        await context.sync();

        documentInfo = {
          hasContent: body.text && body.text.length > 0,
          contentLength: body.text ? body.text.length : 0,
          firstChars: body.text ? body.text.substring(0, 50) : "",
        };

        console.log("Word API test successful:", documentInfo);
        return { available: true, documentInfo };
      } catch (innerError) {
        console.error("Word API inner test failed:", innerError);
        throw innerError;
      }
    });

    return { available: true, documentInfo };
  } catch (e: any) {
    console.error("Word API availability test failed:", e);
    return {
      available: false,
      error: e.message || "Word API not available or not responding",
    };
  }
}
