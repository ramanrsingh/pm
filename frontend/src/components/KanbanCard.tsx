import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import type { Card } from "@/lib/kanban";

type KanbanCardProps = {
  card: Card;
  onDelete: (cardId: string) => void;
};

export const KanbanCard = ({ card, onDelete }: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition: transition ?? undefined,
    willChange: "transform",
  };

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={clsx(
        "group relative select-none rounded-2xl border px-4 py-3.5",
        "transition-[box-shadow,transform,opacity,border-color,background-color] duration-200 ease-out",
        "cursor-grab active:cursor-grabbing",
        isDragging
          ? "border-dashed border-[var(--primary-blue)]/40 bg-[var(--surface)] opacity-30 shadow-none"
          : [
              "border-transparent bg-white",
              "shadow-[0_2px_8px_rgba(3,33,71,0.07),0_1px_2px_rgba(3,33,71,0.04)]",
              "hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(3,33,71,0.12),0_2px_6px_rgba(3,33,71,0.06)]",
            ]
      )}
      {...attributes}
      {...listeners}
      data-testid={`card-${card.id}`}
    >
      <div className="flex items-start justify-between gap-2">
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
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onDelete(card.id)}
          className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[var(--gray-text)] opacity-0 transition-all duration-150 hover:bg-red-50 hover:text-red-400 group-hover:opacity-100"
          aria-label={`Delete ${card.title}`}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
            <path
              d="M8 2L2 8M2 2l6 6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </article>
  );
};
