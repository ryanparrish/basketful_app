import React from 'react';
import { render, screen } from '@testing-library/react';
import WorkflowComponent from '../components/WorkflowComponent';

test('renders WorkflowComponent', () => {
  render(<WorkflowComponent />);
  const headingElement = screen.getByText(/Workflow Component/i);
  expect(headingElement).to.exist;
});