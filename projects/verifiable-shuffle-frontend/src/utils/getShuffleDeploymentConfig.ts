import { ShuffleDeploymentViteConfig } from '../interfaces/deployment'

export function getShuffleDeploymentConfigFromViteEnvironment(): ShuffleDeploymentViteConfig {
  return {
    creatorAddress: import.meta.env.VITE_CREATOR_ADDRESS,
  }
}
