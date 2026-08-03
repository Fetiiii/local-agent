import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { SourceCode } from './SourceCode'

/** Claude-artifacts style HTML preview: rendered in a locked-down iframe
 *  (no same-origin, no top navigation) plus a source view. */
export function HtmlArtifact({ html }: { html: string }) {
  return (
    <Tabs defaultValue="preview">
      <TabsList>
        <TabsTrigger value="preview">Önizleme</TabsTrigger>
        <TabsTrigger value="code">Kod</TabsTrigger>
      </TabsList>
      <TabsContent value="preview">
        <iframe
          title="HTML önizleme"
          srcDoc={html}
          sandbox="allow-scripts"
          className="h-[70vh] w-full rounded-xl border border-border bg-white"
        />
      </TabsContent>
      <TabsContent value="code">
        <SourceCode code={html} lang="html" />
      </TabsContent>
    </Tabs>
  )
}
