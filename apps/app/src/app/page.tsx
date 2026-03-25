"use client";

import { ExampleLayout } from "@/components/example-layout";
import { ExampleCanvas } from "@/components/example-canvas";
import { useGenerativeUIExamples } from "@/hooks";
import { useFileAttachment } from "@/hooks/use-file-attachment";

import { CopilotChat } from "@copilotkit/react-core/v2";

export default function HomePage() {
  useGenerativeUIExamples();

  const {
    fileInputRef,
    openFilePicker,
    onFileInputChange,
    PendingFilesSlot,
    submitWithFiles,
  } = useFileAttachment();

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.csv,.txt"
        multiple
        onChange={onFileInputChange}
      />
      <ExampleLayout
        chatContent={
          <CopilotChat
            onSubmitMessage={submitWithFiles}
            input={{
              // This renders the +/paperclip button next to send.
              onAddFile: openFilePicker,
              // Shows lightweight upload status chips.
              disclaimer: PendingFilesSlot,
              className: "pb-6",
            }}
          />
        }
        appContent={<ExampleCanvas />}
      />
    </>
  );
}
