import { redirect } from '@sveltejs/kit';
export function load({ params }: { params: { id: string } }) {
  redirect(301, `/dashboard/network/loadbalancers/${params.id}`);
}
