export function ImageView({ data }: { data: string }) {
  return (
    <div className="flex justify-center">
      <img src={data} alt="Üretilen görsel" className="max-w-full rounded-lg border border-border" />
    </div>
  )
}
