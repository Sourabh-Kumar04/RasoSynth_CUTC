import { redirect } from 'next/navigation'

export default function Home() {
  // Redirect to working page - not fake pages
  redirect('/datasets')
}
