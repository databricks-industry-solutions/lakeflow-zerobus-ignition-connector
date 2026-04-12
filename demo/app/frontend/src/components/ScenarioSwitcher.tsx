import { api } from '../services/api';

const SCENARIOS = [
  { id: 'wind', label: 'Wind Farm', description: '50 turbines' },
  { id: 'battery', label: 'Battery Site', description: '20 battery units' },
  { id: 'mixed', label: 'Mixed Fleet', description: '30 turbines + 15 batteries' },
] as const;

interface ScenarioSwitcherProps {
  activeScenario: string;
  onScenarioChange: (scenario: string) => void;
}

export default function ScenarioSwitcher({ activeScenario, onScenarioChange }: ScenarioSwitcherProps) {
  const handleClick = async (scenarioId: string) => {
    if (scenarioId === activeScenario) return;
    await api.setScenario(scenarioId);
    onScenarioChange(scenarioId);
  };

  return (
    <div className="flex gap-2">
      {SCENARIOS.map((s) => (
        <button
          key={s.id}
          data-active={s.id === activeScenario}
          onClick={() => handleClick(s.id)}
          className={`px-3 py-1.5 rounded-card text-sm font-medium transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-offset-2 ${
            s.id === activeScenario
              ? 'bg-databricks-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:text-gray-900 hover:bg-gray-200'
          }`}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
