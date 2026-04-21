import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockSetScenario = vi.fn();

vi.mock('../../services/api', () => ({
  api: {
    setScenario: (...args: unknown[]) => mockSetScenario(...args),
  },
}));

import ScenarioSwitcher from '../../components/ScenarioSwitcher';

describe('ScenarioSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSetScenario.mockResolvedValue({ data: { scenario: 'wind' }, meta: { timestamp: '', query_time_ms: 0 } });
  });

  it('renders 3 scenario options (Wind Farm, Battery Site, Mixed Fleet)', () => {
    render(<ScenarioSwitcher activeScenario="mixed" onScenarioChange={vi.fn()} />);

    expect(screen.getByText(/Wind Farm/)).toBeInTheDocument();
    expect(screen.getByText(/Battery Site/)).toBeInTheDocument();
    expect(screen.getByText(/Mixed Fleet/)).toBeInTheDocument();
  });

  it('highlights the active scenario visually', () => {
    const { container } = render(
      <ScenarioSwitcher activeScenario="wind" onScenarioChange={vi.fn()} />,
    );

    const activeButton = container.querySelector('[data-active="true"]');
    expect(activeButton).toBeInTheDocument();
    expect(activeButton?.textContent).toContain('Wind Farm');
  });

  it('calls POST /api/config/scenario when clicking a scenario', async () => {
    const onScenarioChange = vi.fn();
    render(
      <ScenarioSwitcher activeScenario="mixed" onScenarioChange={onScenarioChange} />,
    );

    fireEvent.click(screen.getByText(/Wind Farm/));

    await waitFor(() => {
      expect(mockSetScenario).toHaveBeenCalledWith('wind');
    });
  });
});
