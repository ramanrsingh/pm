import type { Card } from "@/lib/kanban";

type KanbanCardPreviewProps = {
  card: Card;
};

export const KanbanCardPreview = ({ card }: KanbanCardPreviewProps) => (
  <article
    className="rounded-2xl border border-[var(--primary-blue)]/20 bg-white px-4 py-3.5"
    style={{
      transform: "rotate(-1.5deg) scale(1.04)",
      boxShadow:
        "0 28px 56px rgba(3,33,71,0.22), 0 6px 16px rgba(32,157,215,0.18), 0 2px 4px rgba(3,33,71,0.06)",
    }}
  >
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        <h4 className="font-display text-sm font-semibold leading-snug text-[var(--navy-dark)]">
          {card.title}
        </h4>
        {card.details && (
          <p className="mt-1.5 line-clamp-3 text-xs leading-[1.6] text-[var(--gray-text)]">
            {card.details}
          </p>
        )}
      </div>
    </div>
  </article>
);
