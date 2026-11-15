// The score is never shown alone (FR-11, QA-EXP-02): each factor and its
// points are listed like a receipt, and the lines add up to the total.
export function ScoreLedger({ warning }) {
  const { factors, raw_total: rawTotal, score, capped } = warning;
  const name = warning.medicines.join(" and ");
  return (
    <table className="w-full max-w-md border-collapse text-[0.95rem]">
      <caption className="mb-1 text-left font-semibold">How this score was worked out</caption>
      <tbody>
        {factors.map((f) => (
          <tr key={f.code} className="border-b border-dotted border-ink-soft/60">
            <th scope="row" className="py-1 pr-3 text-left font-normal">{f.label}</th>
            <td className="whitespace-nowrap py-1 pl-3 text-right font-semibold">+{f.points}</td>
          </tr>
        ))}
        {capped && (
          <>
            <tr className="border-b border-dotted border-ink-soft/60">
              <th scope="row" className="py-1 pr-3 text-left font-normal">Total of the points above</th>
              <td className="whitespace-nowrap py-1 pl-3 text-right font-semibold">{rawTotal}</td>
            </tr>
            <tr className="border-b border-dotted border-ink-soft/60">
              <th scope="row" className="py-1 pr-3 text-left font-normal">Scores stop at 100</th>
              <td className="whitespace-nowrap py-1 pl-3 text-right font-semibold">100</td>
            </tr>
          </>
        )}
        <tr className="border-t-2 border-ink">
          <th scope="row" className="pt-1.5 pr-3 text-left font-bold">
            Score for {name}
          </th>
          <td className="whitespace-nowrap pt-1.5 pl-3 text-right text-lg font-bold">{score}</td>
        </tr>
      </tbody>
    </table>
  );
}
