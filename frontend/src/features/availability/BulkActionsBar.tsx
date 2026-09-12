import { useTranslation } from "react-i18next";

import { Button } from "../../components/ui/button";

interface BulkActionsBarProps {
  onAllMornings: () => void;
  onAllWeekdayEvenings: () => void;
  onAllWeekends: () => void;
  onClearAll: () => void;
  onCopyLastMonth?: () => void;
}

export function BulkActionsBar({
  onAllMornings,
  onAllWeekdayEvenings,
  onAllWeekends,
  onClearAll,
  onCopyLastMonth,
}: BulkActionsBarProps) {
  const { t } = useTranslation();

  const handleClearAll = () => {
    if (window.confirm(t("availability.bulkConfirmClear"))) {
      onClearAll();
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {onCopyLastMonth && (
        <Button type="button" variant="secondary" size="sm" onClick={onCopyLastMonth}>
          {t("availability.bulkCopyLastMonth")}
        </Button>
      )}
      <Button type="button" variant="secondary" size="sm" onClick={onAllMornings}>
        {t("availability.bulkAllMornings")}
      </Button>
      <Button type="button" variant="secondary" size="sm" onClick={onAllWeekdayEvenings}>
        {t("availability.bulkAllWeekdayEvenings")}
      </Button>
      <Button type="button" variant="secondary" size="sm" onClick={onAllWeekends}>
        {t("availability.bulkAllWeekends")}
      </Button>
      <Button type="button" variant="destructive" size="sm" onClick={handleClearAll}>
        {t("availability.bulkClearAll")}
      </Button>
    </div>
  );
}
