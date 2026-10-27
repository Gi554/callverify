/** In-memory adapter for the real call editor. No network or production callbacks. */
let nextSimulationId = -Date.now()
export function createCallSimulation() {
  const contact: any = {
    id: nextSimulationId--,
    name: 'Camille Tremblay · SIMULATION',
    phone: '+10000000001',
    email: 'camille@example.invalid',
    status: 'to_contact',
    revision: 0,
  }
  const assignment = {
    id: 1,
    advisor_id: 2,
    advisor_name: 'Alex Moreau · SIMULATION',
    setter_id: 1,
    setter_name: 'Setter · SIMULATION',
    active: true,
  }
  const histories: Record<string, any[]> = {
    'call-outcomes': [],
    'follow-ups': [],
    notes: [],
    appointments: [],
    documents: [],
  }
  let qualification: any = {
    age: 38,
    profession: 'full_time',
    marital_status: 'married',
    has_children: true,
    homeowner: true,
    smoker: false,
    has_advisor: false,
    insurances: ['life'],
    additional_notes: 'Données fictives pour explorer la fiche.',
    advisor_notes: 'Préparer une étude de protection familiale.',
  }
  const fields = [
    { key: 'age', label: 'Âge', type: 'number', min: 0, max: 120 },
    {
      key: 'profession',
      label: 'Profession',
      type: 'choice',
      choices: {
        full_time: 'Salarié à temps plein',
        part_time: 'Salarié à temps partiel',
        self_employed: 'Travailleur autonome',
        retired: 'Retraité',
        other: 'Autre',
      },
    },
    {
      key: 'marital_status',
      label: 'Situation matrimoniale',
      type: 'choice',
      choices: {
        married: 'Marié',
        single: 'Célibataire',
        common_law: 'Conjoint de fait',
        other: 'Autre',
      },
    },
    ...Object.entries({
      has_children: 'A des enfants',
      homeowner: 'Est propriétaire',
      smoker: 'Fumeur',
      has_advisor: 'Possède un conseiller',
    }).map(([key, label]) => ({ key, label, type: 'boolean' })),
    {
      key: 'insurances',
      label: 'Assurances détenues',
      type: 'multiple',
      choices: {
        life: 'Assurance vie',
        disability: 'Invalidité',
        critical_illness: 'Maladies graves',
        group: 'Assurances collectives',
        none_known: 'Aucune connue',
      },
    },
    { key: 'additional_notes', label: 'Notes complémentaires', type: 'text' },
    { key: 'advisor_notes', label: 'Notes utiles au conseiller', type: 'text' },
  ]
  const copy = (value: any) => structuredClone(value)
  const list = (rows: any[]) => ({
    results: copy(rows),
    count: rows.length,
    next: null,
    previous: null,
  })
  const stages = [
    ['to_contact', 'À contacter'],
    ['in_progress', 'En cours'],
    ['callback', 'À rappeler'],
    ['interested', 'Intéressé'],
    ['follow_up', 'Suivi'],
    ['closed', 'Clôturé'],
  ].map(([key, label]) => ({ key, label, active: true }))
  const labels: Record<string, string> = {
    voicemail: 'Répondeur',
    invalid_number: 'Numéro invalide',
    disconnected: 'Appel coupé',
    not_interested: 'Pas intéressé',
    callback: 'A demandé à être rappelé',
    unreachable: 'Injoignable',
    appointment_booked: 'Rendez-vous pris',
  }
  let calls = 0
  async function request(path: string, body?: any, method?: string): Promise<any> {
    const clean = path.split('?')[0]!
    const write = body !== undefined
    const resource = clean.replace(/^contacts\/-\d+\//, '')
    if (clean === 'pipeline/') return { stages }
    if (resource === 'lease/')
      return method === 'DELETE'
        ? null
        : {
            locked: true,
            mine: true,
            token: 'simulation-only',
            expires_at: new Date(Date.now() + 3600000).toISOString(),
          }
    if (resource === '') {
      if (write) {
        Object.assign(contact, { name: body.name, phone: body.phone, email: body.email })
        contact.revision++
      }
      return copy(contact)
    }
    if (resource === 'qualification/') {
      if (write) {
        qualification = copy(body.qualification)
        contact.revision++
      }
      return {
        fields: copy(fields),
        qualification: copy(qualification),
        revision: contact.revision,
      }
    }
    if (resource === 'custom_fields/')
      return { schema: { fields: [] }, values: {}, contact_revision: contact.revision }
    if (resource === 'call-intent/' || resource === 'phone-history-proof/')
      return { proof: 'simulation-only' }
    if (resource === 'commercial-status/') {
      contact.status = body.status
      contact.revision++
      return copy(contact)
    }
    for (const key of ['call-outcomes', 'follow-ups', 'notes', 'documents']) {
      if (resource === key + '/') {
        if (write) {
          const row = {
            ...copy(body),
            id: histories[key]!.length + 1,
            created_at: new Date().toISOString(),
            label: labels[body.result] || '',
            reason: body.reason || body.note || '',
            author_name: 'Setter · SIMULATION',
            revision: 0,
          }
          histories[key]!.unshift(row)
          if (key === 'call-outcomes' && body.result === 'callback')
            histories['follow-ups']!.unshift({ ...row, id: histories['follow-ups']!.length + 1 })
          return copy(row)
        }
        return list(histories[key]!)
      }
    }
    if (resource === 'history/') return list(histories['call-outcomes']!)
    if (clean === 'assignments/') return list([assignment])
    if (clean === 'advisor-usage/')
      return list([{ advisor_id: 2, booked: histories.appointments!.length, attended: 0 }])
    if (clean === 'appointments/availability/') return { busy: [], working_hours_enabled: false }
    if (clean === 'appointments/') {
      if (write) {
        const row = {
          ...copy(body),
          id: histories.appointments!.length + 1,
          contact: contact.id,
          contact_name: contact.name,
          contact_phone: contact.phone,
          advisor_id: 2,
          advisor_name: assignment.advisor_name,
          setter_name: assignment.setter_name,
          status: 'scheduled',
          business_status: 'scheduled',
          report: null,
          calendar: 'internal',
          revision: 0,
          qualification_snapshot: {
            contact: copy(contact),
            qualification: copy(qualification),
            captured_at: new Date().toISOString(),
          },
        }
        histories.appointments!.unshift(row)
        return copy(row)
      }
      return list(histories.appointments!)
    }
    throw new Error(
      'Cette action ne fait pas partie de la simulation. Aucun appel réseau effectué.',
    )
  }
  async function portal(path: string, body?: any): Promise<any> {
    if (path === 'assurance/calls/options/')
      return { enabled: true, post_associated: true, call_window: { allowed: true } }
    if (path === 'assurance/calls/' && body?.proof === 'simulation-only') {
      calls++
      await new Promise((resolve) => setTimeout(resolve, 700))
      return {
        state: 'accepted',
        definition:
          'SIMULATION : le poste a répondu et la composition serait lancée. Aucun appel réel, aucun audio.',
      }
    }
    if (/^assurance\/calls\/[a-f0-9-]+\/$/.test(path))
      return {
        state: 'accepted',
        definition: 'Commande fictive conservée uniquement dans cet aperçu.',
      }
    if (path === 'assurance/phone-history/') return list([])
    if (path === 'assurance/advisor-quotas/')
      return list([{ id: 2, name: assignment.advisor_name, quota: 20 }])
    if (path.includes('calendly'))
      return { configured: false, connected: false, booking_in_crm: false, event_types: [] }
    throw new Error('Service externe indisponible en simulation ; aucun appel réseau effectué.')
  }
  return { contact, request, portal, callCount: () => calls }
}
