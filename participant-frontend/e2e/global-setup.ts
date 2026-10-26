import { seedE2eParticipant } from './support/seed';

export default function globalSetup() {
  if (process.env.E2E_SKIP_SEED) return;
  seedE2eParticipant();
}
