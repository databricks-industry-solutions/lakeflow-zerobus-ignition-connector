import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../../components/ScenarioSwitcher', () => ({
  default: () => <div data-testid="scenario-switcher" />,
}));

vi.mock('../../components/ResetDialog', () => ({
  default: () => <div data-testid="reset-dialog" />,
}));

import Header from '../../components/Header';

describe('Header', () => {
  it('displays active scenario name for wind', () => {
    render(
      <Header
        activeScenario="wind"
        onScenarioChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/Wind Farm/)).toBeInTheDocument();
  });

  it('displays battery scenario name', () => {
    render(
      <Header
        activeScenario="battery"
        onScenarioChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/Battery Site/)).toBeInTheDocument();
  });

  it('displays mixed fleet scenario name', () => {
    render(
      <Header
        activeScenario="mixed"
        onScenarioChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/Mixed Fleet/)).toBeInTheDocument();
  });
});
