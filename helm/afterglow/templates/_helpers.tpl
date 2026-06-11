{{/*
Release 네임스페이스 (helm install -n <ns> 으로 주입)
*/}}
{{- define "afterglow.namespace" -}}
{{ .Release.Namespace }}
{{- end }}

{{/*
공통 레이블
*/}}
{{- define "afterglow.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
