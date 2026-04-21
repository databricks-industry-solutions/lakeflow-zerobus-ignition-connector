import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ArchitectureDiagram from '../../components/ArchitectureDiagram';

describe('ArchitectureDiagram', () => {
  it('Before diagram renders traditional stack components (Interface, Buffer, Server, Archive)', () => {
    render(<ArchitectureDiagram />);

    expect(screen.getByText(/^Interface$/)).toBeInTheDocument();
    expect(screen.getByText(/^Buffer$/)).toBeInTheDocument();
    expect(screen.getByText(/^Server$/)).toBeInTheDocument();
    expect(screen.getByText(/^Archive$/)).toBeInTheDocument();
  });

  it('After diagram renders Lakehouse components and highlights "No Kafka", "No Buffer Nodes", "No Archive Servers", "Open Format"', () => {
    render(<ArchitectureDiagram />);

    // Lakehouse components
    expect(screen.getByText(/Ignition/)).toBeInTheDocument();
    expect(screen.getByText(/Zerobus Connector/)).toBeInTheDocument();
    expect(screen.getByText(/Delta Lake/)).toBeInTheDocument();

    // Highlights
    expect(screen.getByText(/No Kafka/)).toBeInTheDocument();
    expect(screen.getByText(/No Buffer Nodes/)).toBeInTheDocument();
    expect(screen.getByText(/No Archive Servers/)).toBeInTheDocument();
    expect(screen.getByText(/Open Format/)).toBeInTheDocument();
  });
});
