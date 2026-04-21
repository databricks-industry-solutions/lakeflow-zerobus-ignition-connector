import ScenarioSwitcher from './ScenarioSwitcher';
import ResetDialog from './ResetDialog';

const SCENARIO_LABELS: Record<string, string> = {
  wind: 'Wind Farm',
  battery: 'Battery Site',
  mixed: 'Mixed Fleet',
};

interface HeaderProps {
  activeScenario: string;
  onScenarioChange: (scenario: string) => void;
}

export default function Header({ activeScenario, onScenarioChange }: HeaderProps) {
  return (
    <header className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">Active scenario:</span>
        <span className="text-sm font-medium text-databricks-primary">
          {SCENARIO_LABELS[activeScenario] ?? activeScenario}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <ScenarioSwitcher
          activeScenario={activeScenario}
          onScenarioChange={onScenarioChange}
        />
        <ResetDialog />
      </div>
    </header>
  );
}
