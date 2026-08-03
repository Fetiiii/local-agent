import { SourceCode } from './SourceCode'

export function TextView({ text }: { text: string }) {
  return <SourceCode code={text} lang="text" />
}
