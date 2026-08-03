import type { Artifact } from '@/lib/types'
import { ImageView } from './ImageView'
import { PlotlyView } from './PlotlyView'
import { TableView } from './TableView'
import { LinksView } from './LinksView'
import { TextView } from './TextView'
import { FileArtifact } from './FileArtifact'

export function ArtifactView({ artifact }: { artifact: Artifact }) {
  switch (artifact.type) {
    case 'image':
      return <ImageView data={artifact.data} />
    case 'plotly':
      return <PlotlyView json={artifact.json} />
    case 'table':
      return <TableView html={artifact.html} />
    case 'links':
      return <LinksView items={artifact.items} />
    case 'text':
      return <TextView text={artifact.text} />
    case 'file':
      return <FileArtifact file={artifact} />
  }
}
