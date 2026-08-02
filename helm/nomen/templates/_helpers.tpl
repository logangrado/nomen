{{/*
Expand the name of the chart.
*/}}
{{- define "nomen.name" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "nomen.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "nomen.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels used by the Deployment and Service.
*/}}
{{- define "nomen.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nomen.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Full image reference.
*/}}
{{- define "nomen.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{- end }}

{{/*
Runtime env vars sourced from the configured secret.
*/}}
{{- define "nomen.secretEnv" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.env.secretName }}
      key: {{ .Values.env.keys.databaseUrl }}
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.env.secretName }}
      key: {{ .Values.env.keys.secretKey }}
- name: USER_1
  valueFrom:
    secretKeyRef:
      name: {{ .Values.env.secretName }}
      key: {{ .Values.env.keys.user1 }}
- name: USER_2
  valueFrom:
    secretKeyRef:
      name: {{ .Values.env.secretName }}
      key: {{ .Values.env.keys.user2 }}
{{- end }}
