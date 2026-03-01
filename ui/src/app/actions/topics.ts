'use server'

import { createServiceClient } from '@/lib/supabase/server'
import { revalidatePath } from 'next/cache'

export async function approveTopic(topicId: string) {
  const supabase = await createServiceClient()
  await supabase
    .from('topics')
    .update({ status: 'approved', updated_at: new Date().toISOString() })
    .eq('id', topicId)
  revalidatePath('/topics')
}

export async function rejectTopic(topicId: string, reason: string) {
  const supabase = await createServiceClient()
  await supabase
    .from('topics')
    .update({
      status: 'rejected',
      rejected_reason: reason || null,
      updated_at: new Date().toISOString(),
    })
    .eq('id', topicId)
  revalidatePath('/topics')
}

export async function bulkApprove(topicIds: string[]) {
  const supabase = await createServiceClient()
  await supabase
    .from('topics')
    .update({ status: 'approved', updated_at: new Date().toISOString() })
    .in('id', topicIds)
  revalidatePath('/topics')
}

export async function bulkReject(topicIds: string[], reason: string) {
  const supabase = await createServiceClient()
  await supabase
    .from('topics')
    .update({
      status: 'rejected',
      rejected_reason: reason || null,
      updated_at: new Date().toISOString(),
    })
    .in('id', topicIds)
  revalidatePath('/topics')
}
