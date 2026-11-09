import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export interface LibraryPermissionRow {
  user_id: number
  username: string
  can_edit: boolean
  can_upload: boolean
  can_share: boolean
  can_manage: boolean
}

export interface LibraryPermissionOverview {
  owner: string | null
  owner_id: number | null
  puoi_gestire: boolean
  condivisioni: LibraryPermissionRow[]
}

export interface PermissionTarget {
  id: number
  username: string
}

export async function fetchLibraryPermissions(folder: string): Promise<LibraryPermissionOverview> {
  const { data, error } = await api.GET('/api/kolibre/libraries/{name}/permessi', {
    params: { path: { name: folder } },
  })
  if (error) throw error
  return data as LibraryPermissionOverview
}

export function useLibraryPermissions(folder: string, enabled: boolean) {
  return useQuery({
    queryKey: ['library-permissions', folder],
    queryFn: () => fetchLibraryPermissions(folder),
    enabled,
  })
}

export function usePermissionTargets(enabled: boolean) {
  return useQuery({
    queryKey: ['permission-target-users'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/users')
      if (error) throw error
      return (data ?? []).map((user) => ({ id: user.id, username: user.username })) as PermissionTarget[]
    },
    enabled,
  })
}

export async function saveLibraryPermission(folder: string, row: Omit<LibraryPermissionRow, 'username'>) {
  const { error } = await api.PUT('/api/kolibre/libraries/{name}/permessi', {
    params: { path: { name: folder } },
    body: row,
  })
  if (error) throw error
}

export async function revokeLibraryPermission(folder: string, userId: number) {
  const { error } = await api.PUT('/api/kolibre/libraries/{name}/permessi', {
    params: { path: { name: folder } },
    body: { user_id: userId, revoca: true },
  })
  if (error) throw error
}
