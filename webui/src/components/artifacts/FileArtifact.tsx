import { FileWarning } from 'lucide-react'
import type { Artifact } from '@/lib/types'
import { Markdown } from '@/lib/markdown'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { HtmlArtifact } from './HtmlArtifact'
import { TableView } from './TableView'
import { SourceCode } from './SourceCode'

type FileArt = Extract<Artifact, { type: 'file' }>

function PathNote({ file, note }: { file: FileArt; note?: string }) {
  return (
    <div className="rounded-xl border border-border bg-panel-2 p-4 text-sm">
      <div className="mb-1 flex items-center gap-2 text-muted">
        <FileWarning size={16} />
        {note ?? 'Bu dosya önizlenemiyor.'}
      </div>
      <code className="break-all text-[12.5px] text-patina">{file.path}</code>
    </div>
  )
}

export function FileArtifact({ file }: { file: FileArt }) {
  switch (file.kind) {
    case 'html':
      return file.text ? <HtmlArtifact html={file.text} /> : <PathNote file={file} />

    case 'markdown':
      return file.text ? (
        <Tabs defaultValue="preview">
          <TabsList>
            <TabsTrigger value="preview">Önizleme</TabsTrigger>
            <TabsTrigger value="code">Kaynak</TabsTrigger>
          </TabsList>
          <TabsContent value="preview">
            <div className="rounded-xl border border-border bg-panel-2 p-4">
              <Markdown>{file.text}</Markdown>
            </div>
          </TabsContent>
          <TabsContent value="code">
            <SourceCode code={file.text} lang="markdown" />
          </TabsContent>
        </Tabs>
      ) : (
        <PathNote file={file} />
      )

    case 'csv':
      return (
        <Tabs defaultValue="table">
          <TabsList>
            <TabsTrigger value="table">Tablo</TabsTrigger>
            <TabsTrigger value="code">Kaynak</TabsTrigger>
          </TabsList>
          <TabsContent value="table">
            {file.table_html ? <TableView html={file.table_html} /> : <PathNote file={file} />}
          </TabsContent>
          <TabsContent value="code">
            {file.text ? <SourceCode code={file.text} lang="csv" /> : <PathNote file={file} />}
          </TabsContent>
        </Tabs>
      )

    case 'excel':
      return file.table_html ? <TableView html={file.table_html} /> : <PathNote file={file} />

    case 'pdf':
      return file.data ? (
        <iframe title="PDF önizleme" src={file.data} className="h-[75vh] w-full rounded-xl border border-border" />
      ) : (
        <PathNote file={file} note="PDF önizleme için çok büyük." />
      )

    case 'text':
      return file.text ? <SourceCode code={file.text} lang="text" /> : <PathNote file={file} />

    default:
      return <PathNote file={file} />
  }
}
