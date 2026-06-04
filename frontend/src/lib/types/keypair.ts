export interface Keypair {
  name: string;
  fingerprint: string;
  type: string;
  public_key?: string;
  private_key?: string;
}
