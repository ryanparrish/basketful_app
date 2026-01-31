import { render, screen } from '@testing-library/react';
import ResourceComponent from '../components/ResourceComponent';

test('renders ResourceComponent', () => {
  render(<ResourceComponent />);
  const headingElement = screen.getByText(/Resource Component/i);
  expect(headingElement).toBeInTheDocument();
});