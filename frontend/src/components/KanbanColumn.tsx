import clsx from "clsx";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Card, Column } from "@/lib/kanban";
import { KanbanCard } from "@/components/KanbanCard";
import { NewCardForm } from "@/components/NewCardForm";

const COLUMN_ACCENTS = [
  { color: "#209dd7", label: "blue" },
  { color: "#ecad0a", label: "yellow" },
  { color: "#753991", label: "purple" },
  { color: "#0ea5a0", label: "teal" },
  { color: "#e07c3a", label: "orange" },
];

type KanbanColumnProps = {
  column: Column;
  cards: Card[];
  index: number;
  onRename: (columnId: string, title: string) => void;
  onAddCard: (columnId: string, title: string, details: string) => void;
  onDeleteCard: (columnId: string, cardId: string) => void;
};

export const KanbanColumn = ({
  column,
  cards,
  index,
  onRename,
  onAddCard,
  onDeleteCard,
}: KanbanColumnProps) => {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const accent = COLUMN_ACCENTS[index % COLUMN_ACCENTS.length];

  return (
    <section
      ref={setNodeRef}
      className={clsx(
        "flex min-h-[520px] flex-col rounded-3xl border bg-[var(--surface-strong)] p-4 transition-all duration-200",
        isOver
          ? "border-[var(--accent-yellow)] shadow-[0_0_0_2px_rgba(236,173,10,0.25),var(--shadow-lg)]"
          : "border-[var(--stroke)] shadow-[var(--shadow)]"
      )}
      data-testid={`column-${column.id}`}
    >
      {/* Colored top accent strip */}
      <div
        className="mb-4 h-[3px] w-full rounded-full transition-all duration-200"
        style={{
          background: isOver
            ? "var(--accent-yellow)"
            : accent.color,
        }}
      />

      <div className="flex items-start gap-3">
        <div className="w-full">
          <div className="flex items-center gap-2">
            <span
              className="flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 text-[10px] font-bold text-white"
              style={{ background: accent.color }}
            >
              {cards.length}
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--gray-text)]">
              cards
            </span>
          </div>
          <input
            value={column.title}
            onChange={(event) => onRename(column.id, event.target.value)}
            className="mt-2 w-full bg-transparent font-display text-base font-semibold text-[var(--navy-dark)] outline-none transition-colors duration-150 hover:text-[var(--primary-blue)] focus:text-[var(--primary-blue)]"
            aria-label="Column title"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-1 flex-col gap-2.5">
        <SortableContext items={column.cardIds} strategy={verticalListSortingStrategy}>
          {cards.map((card) => (
            <KanbanCard
              key={card.id}
              card={card}
              onDelete={(cardId) => onDeleteCard(column.id, cardId)}
            />
          ))}
        </SortableContext>
        {cards.length === 0 && (
          <div
            className={clsx(
              "flex flex-1 items-center justify-center rounded-2xl border border-dashed px-3 py-6 text-center transition-all duration-200",
              "text-xs font-semibold uppercase tracking-[0.18em]",
              isOver
                ? "border-[var(--accent-yellow)] bg-[rgba(236,173,10,0.04)] text-[var(--accent-yellow)]"
                : "border-[var(--stroke)] text-[var(--gray-text)]"
            )}
          >
            {isOver ? "Release to drop" : "Drop a card here"}
          </div>
        )}
      </div>

      <NewCardForm onAdd={(title, details) => onAddCard(column.id, title, details)} />
    </section>
  );
};
