export type CaregiverTab = "attention" | "all" | "medication" | "timeline";

const TAB_LABELS: Record<CaregiverTab, string> = {
  attention: "Needs Attention",
  all: "All Memories",
  medication: "Medication",
  timeline: "Timeline",
};

export function TabBar({
  active,
  counts,
  onChange,
}: {
  active: CaregiverTab;
  counts: Partial<Record<CaregiverTab, number>>;
  onChange: (tab: CaregiverTab) => void;
}) {
  const tabs: CaregiverTab[] = ["attention", "all", "medication", "timeline"];

  return (
    <div className="flex gap-2 border-b border-slate-200">
      {tabs.map((tab) => {
        const isActive = tab === active;
        const count = counts[tab];
        return (
          <button
            key={tab}
            type="button"
            onClick={() => onChange(tab)}
            className={`flex items-center gap-2 rounded-t-lg px-4 py-2 text-sm font-medium transition-colors ${
              isActive
                ? "border-b-2 border-rose-600 text-rose-700"
                : "text-slate-500 hover:text-slate-800"
            }`}
          >
            {TAB_LABELS[tab]}
            {count !== undefined && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  isActive ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-500"
                }`}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
