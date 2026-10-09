import com.onresolve.scriptrunner.runner.rest.common.CustomEndpointDelegate
import groovy.json.JsonBuilder
import groovy.json.JsonSlurper
import groovy.transform.BaseScript

import com.atlassian.jira.component.ComponentAccessor
import com.atlassian.jira.issue.fields.CustomField
import com.atlassian.jira.issue.fields.config.FieldConfigScheme
import com.atlassian.jira.issue.fields.screen.*
import com.atlassian.jira.issue.fields.screen.issuetype.*
import com.atlassian.jira.issue.fields.layout.field.*
import com.atlassian.jira.issue.issuetype.IssueType
import com.atlassian.jira.workflow.JiraWorkflow
import com.atlassian.jira.project.Project
import com.atlassian.jira.notification.NotificationSchemeManager
import com.atlassian.jira.security.roles.ProjectRoleManager
import com.atlassian.jira.config.IssueTypeManager
import com.atlassian.jira.config.StatusManager
import com.atlassian.jira.config.PriorityManager
import com.atlassian.jira.config.ResolutionManager
import com.opensymphony.workflow.loader.*

import javax.ws.rs.core.MultivaluedMap
import javax.ws.rs.core.Response

@BaseScript CustomEndpointDelegate delegate

// ============================================================================
//  atlassian-admin-mcp — read-only admin endpoint (Jira DC 9.x / 10.x)
//  URL:    GET /rest/scriptrunner/latest/custom/atlassianAdmin?action=...
//  Access: members of ALLOWED_GROUPS only
// ============================================================================

// Bumped whenever actions are added or change shape; reported by ?action=ping.
final String ENDPOINT_VERSION = "2.0.0"

// Groups allowed to call this endpoint. Adjust if your admin group differs.
final List<String> ALLOWED_GROUPS = ["jira-administrators"]

atlassianAdmin(httpMethod: "GET", groups: ALLOWED_GROUPS) { MultivaluedMap queryParams ->
    def action = queryParams.getFirst("action") ?: ""
    def p = { String name -> queryParams.getFirst(name) ?: "" }

    try {
        switch (action) {
            case "ping":
                return ok([
                    ok             : true,
                    endpointVersion: ENDPOINT_VERSION,
                    allowedGroups  : ALLOWED_GROUPS,
                    jiraVersion    : ComponentAccessor.getComponent(com.atlassian.jira.util.BuildUtilsInfo)?.version,
                    user           : ComponentAccessor.jiraAuthenticationContext?.loggedInUser?.name,
                ])
            case "list_custom_fields":       return listCustomFields(p("search"))
            case "get_custom_field":         return getCustomField(p("id"))
            case "get_field_options":        return getFieldOptions(p("id"), p("contextId"))
            case "list_system_fields":       return listSystemFields()
            case "list_custom_field_types":  return listCustomFieldTypes()
            case "list_workflows":           return listWorkflows(p("search"))
            case "get_workflow":             return getWorkflow(p("name"))
            case "get_workflow_transition":  return getWorkflowTransition(p("name"), p("transitionId"))
            case "get_workflow_xml":         return getWorkflowXml(p("name"))
            case "list_screens":             return listScreens(p("search"))
            case "get_screen":               return getScreen(p("id"))
            case "list_screen_schemes":      return listScreenSchemes(p("search"))
            case "list_issue_type_screen_schemes": return listIssueTypeScreenSchemes(p("search"))
            case "list_permission_schemes":  return listPermissionSchemes()
            case "get_permission_scheme":    return getPermissionScheme(p("id"))
            case "list_notification_schemes": return listNotificationSchemes()
            case "get_notification_scheme":  return getNotificationScheme(p("id"))
            case "list_workflow_schemes":    return listWorkflowSchemes()
            case "get_workflow_scheme":      return getWorkflowScheme(p("id"))
            case "list_projects":            return listProjects(p("search"))
            case "get_project_config":       return getProjectConfig(p("key"))
            case "list_groups":              return listGroups(p("search"))
            case "get_group_members":        return getGroupMembers(p("group"))
            case "list_project_roles":       return listProjectRoles()
            case "get_project_role_members": return getProjectRoleMembers(p("project"), p("roleId"))
            case "get_user":                 return getUser(p("username"), p("key"))
            case "list_application_roles":   return listApplicationRoles()
            case "list_issue_types":         return listIssueTypes()
            case "list_issue_type_schemes":  return listIssueTypeSchemes(p("search"))
            case "list_reference_data":      return listReferenceData()
            case "list_field_configurations":  return listFieldConfigurations(p("search"))
            case "get_field_configuration":    return getFieldConfiguration(p("id"))
            case "list_field_config_schemes":  return listFieldConfigSchemes(p("search"))
            case "get_field_config_scheme":    return getFieldConfigScheme(p("id"))

            // Issue Link Types
            case "list_issue_link_types":     return listIssueLinkTypes()

            // Issue Security Schemes
            case "list_issue_security_schemes": return listIssueSecuritySchemes()
            case "get_issue_security_scheme": return getIssueSecurityScheme(p("id"))

            // Global Config & Metadata
            case "get_server_info":           return getServerInfo()
            case "get_application_properties": return getApplicationProperties(p("search"))
            case "list_project_categories":   return listProjectCategories()
            case "list_event_types":          return listEventTypes()
            case "list_global_permissions":   return listGlobalPermissions()

            // Shared Filters & Dashboards
            case "list_shared_filters":       return listSharedFilters(p("search"))
            case "list_dashboards":           return listDashboards(p("search"))

            // Cluster (DC)
            case "get_cluster_info":          return getClusterInfo()

            // Priority Schemes (10.x)
            case "list_priority_schemes":     return listPrioritySchemes()

            // Assets (Insight / CMDB)
            case "list_object_schemas":       return listObjectSchemas()
            case "get_object_schema":         return getObjectSchema(p("id"))
            case "list_object_types":         return listObjectTypes(p("schemaId"))
            case "get_object_type_attributes": return getObjectTypeAttributes(p("id"))
            case "aql_search":               return aqlSearch(p("schema"), p("aql"), p("maxResults"))
            case "get_asset_object":         return getAssetObject(p("id"))
            case "list_reference_types":     return listReferenceTypes(p("schemaId"))
            case "list_status_types":        return listStatusTypes(p("schemaId"))
            case "list_import_configs":      return listImportConfigs(p("schemaId"))
            case "get_object_connected_tickets": return getObjectConnectedTickets(p("id"))

            // Issue Worklogs
            case "get_issue_worklogs":           return getIssueWorklogs(p("key"))

            // ScriptRunner Configuration (all list-tools accept optional project= filter)
            case "list_sr_listeners":            return listSrListeners(p("project"))
            case "get_sr_listener":              return getSrListener(p("id"))
            case "list_sr_behaviours":           return listSrBehaviours(p("project"))
            case "get_sr_behaviour":             return getSrBehaviour(p("id"))
            case "list_sr_script_fields":        return listSrScriptFields(p("project"))
            case "get_sr_script_field":          return getSrScriptField(p("id"))
            case "list_sr_fragments":            return listSrFragments()
            case "list_sr_jobs":                 return listSrJobs(p("project"))
            case "list_sr_endpoints":            return listSrEndpoints()
            case "list_sr_escalation_services":  return listSrEscalationServices(p("project"))
            case "get_sr_escalation_service":    return getSrEscalationService(p("id"))

            // JMWE Event-Based Actions
            case "list_jmwe_event_actions":       return listJmweEventActions(p("project"))
            case "get_jmwe_event_action":         return getJmweEventAction(p("id"))

            // JMWE Shared Actions (reusable post-functions/conditions/validators in workflows)
            case "list_jmwe_shared_actions":      return listJmweSharedActions(p("type"))
            case "get_jmwe_shared_action":        return getJmweSharedAction(p("id"))

            // Structure Plugin
            case "list_structures":              return listStructures(p("search"))
            case "get_structure":                return getStructure(p("id"))
            case "list_structure_views":          return listStructureViews(p("search"))
            case "get_structure_view":            return getStructureView(p("id"))

            // System Log (audit log accessed via REST API from Python side)
            case "get_system_log":               return getSystemLog(p("lines"), p("search"))

            default:
                return badRequest([
                    error: "Unknown action: '${action}'",
                    hint : "Call with ?action=list_custom_fields (or any valid action)",
                    actions: [
                        "Custom Fields"       : ["list_custom_fields", "get_custom_field", "get_field_options", "list_system_fields", "list_custom_field_types"],
                        "Workflows"           : ["list_workflows", "get_workflow", "get_workflow_transition", "get_workflow_xml"],
                        "Screens"             : ["list_screens", "get_screen", "list_screen_schemes", "list_issue_type_screen_schemes"],
                        "Permission Schemes"  : ["list_permission_schemes", "get_permission_scheme"],
                        "Notification Schemes": ["list_notification_schemes", "get_notification_scheme"],
                        "Workflow Schemes"    : ["list_workflow_schemes", "get_workflow_scheme"],
                        "Issue Security"      : ["list_issue_security_schemes", "get_issue_security_scheme"],
                        "Issue Link Types"    : ["list_issue_link_types"],
                        "Projects"            : ["list_projects", "get_project_config"],
                        "Users & Groups"      : ["list_groups", "get_group_members", "list_project_roles", "get_project_role_members", "get_user", "list_application_roles"],
                        "Issue Types"         : ["list_issue_types", "list_issue_type_schemes", "list_reference_data"],
                        "Field Configurations": ["list_field_configurations", "get_field_configuration", "list_field_config_schemes", "get_field_config_scheme"],
                        "Global Config"       : ["get_server_info", "get_application_properties", "list_project_categories", "list_event_types", "list_global_permissions"],
                        "Filters & Dashboards": ["list_shared_filters", "list_dashboards"],
                        "Cluster (DC)"        : ["get_cluster_info"],
                        "Priority Schemes"    : ["list_priority_schemes"],
                        "Assets (CMDB)"       : ["list_object_schemas", "get_object_schema", "list_object_types", "get_object_type_attributes", "aql_search", "get_asset_object", "list_reference_types", "list_status_types", "list_import_configs", "get_object_connected_tickets"],
                        "Issue Worklogs"      : ["get_issue_worklogs"],
                        "ScriptRunner Config" : ["list_sr_listeners", "get_sr_listener", "list_sr_behaviours", "get_sr_behaviour", "list_sr_script_fields", "get_sr_script_field", "list_sr_fragments", "list_sr_jobs", "list_sr_endpoints", "list_sr_escalation_services", "get_sr_escalation_service"],
                        "JMWE"                : ["list_jmwe_event_actions", "get_jmwe_event_action", "list_jmwe_shared_actions", "get_jmwe_shared_action"]
                    ]
                ])
        }
    } catch (Exception e) {
        return Response.status(500)
            .entity(new JsonBuilder([error: e.message, stackTrace: e.stackTrace?.take(5)?.collect { it.toString() }, action: action]).toString())
            .header("Content-Type", "application/json").build()
    }
}


// ============================================================================
//  HELPERS — 10.3.2 safe scheme lookup (avoids getSchemes(project) GenericValue)
// ============================================================================

def findSchemeForProject(schemeManager, Project project) {
    try {
        schemeManager.schemeObjects.find { scheme ->
            schemeManager.getProjects(scheme)?.any { it.id == project.id }
        }
    } catch (Exception e) { null }
}

def schemeInfo(scheme) {
    scheme ? [id: scheme.id, name: scheme.name] : null
}


// ============================================================================
//  CUSTOM FIELDS
// ============================================================================

def listCustomFields(String search) {
    def cfManager = ComponentAccessor.customFieldManager
    def fields = cfManager.customFieldObjects
    if (search) fields = fields.findAll { it.name.toLowerCase().contains(search.toLowerCase()) }

    ok(fields.collect { CustomField cf ->
        [id: cf.id, name: cf.name, type: cf.customFieldType?.key ?: "unknown",
         typeName: cf.customFieldType?.name ?: "unknown", description: cf.description ?: "",
         searcherKey: cf.customFieldSearcher?.descriptor?.completeKey ?: "",
         contexts: cf.configurationSchemes?.size() ?: 0]
    }.sort { it.name })
}

def getCustomField(String fieldId) {
    def cfManager = ComponentAccessor.customFieldManager
    def cf = cfManager.getCustomFieldObject(fieldId)
    if (!cf) return notFound("Field not found: ${fieldId}")

    def contexts = cf.configurationSchemes?.collect { FieldConfigScheme scheme ->
        def projects = []
        try {
            projects = scheme.contexts?.findAll { it.projectObject }?.collect {
                [id: it.projectObject.id, key: it.projectObject.key, name: it.projectObject.name]
            } ?: []
        } catch (Exception e) {}

        def issueTypes = []
        try {
            issueTypes = scheme.associatedIssueTypeObjects?.collect {
                it ? [id: it.id, name: it.name] : [id: "all", name: "All Issue Types"]
            } ?: []
        } catch (Exception e) {}

        [id: scheme.id, name: scheme.name ?: "Context #${scheme.id}", isGlobal: projects.isEmpty(),
         projects: projects, issueTypes: issueTypes, fieldConfigId: scheme.oneAndOnlyConfig?.id]
    } ?: []

    ok([id: cf.id, name: cf.name, type: cf.customFieldType?.key ?: "unknown",
        typeName: cf.customFieldType?.name ?: "unknown", description: cf.description ?: "",
        searcherKey: cf.customFieldSearcher?.descriptor?.completeKey ?: "",
        isAllProjects: contexts.any { it.isGlobal }, contexts: contexts])
}

def getFieldOptions(String fieldId, String contextId) {
    def cfManager = ComponentAccessor.customFieldManager
    def optionsManager = ComponentAccessor.optionsManager
    def cf = cfManager.getCustomFieldObject(fieldId)
    if (!cf) return notFound("Field not found: ${fieldId}")

    def allOptions = []
    for (scheme in (cf.configurationSchemes ?: [])) {
        if (contextId && scheme.id.toString() != contextId) continue
        def config = scheme.oneAndOnlyConfig
        if (!config) continue
        def options = optionsManager.getOptions(config)
        if (!options) continue

        allOptions << [contextId: scheme.id, contextName: scheme.name ?: "Context #${scheme.id}",
            options: options.collect { opt ->
                def entry = [id: opt.optionId, value: opt.value, disabled: opt.disabled, sequence: opt.sequence]
                if (opt.childOptions) {
                    entry.children = opt.childOptions.collect { child ->
                        [id: child.optionId, value: child.value, disabled: child.disabled]
                    }
                }
                entry
            }
        ]
    }
    ok(allOptions)
}

def listSystemFields() {
    ok(ComponentAccessor.fieldManager.allAvailableNavigableFields
        .findAll { !it.id.startsWith("customfield_") }
        .collect { [id: it.id, name: it.name] }
        .sort { it.name })
}

def listCustomFieldTypes() {
    def cfManager = ComponentAccessor.customFieldManager
    try {
        def types = cfManager.customFieldTypes
        ok(types?.collect {
            [key: it.key, name: it.name, description: it.description ?: ""]
        }?.sort { it.name } ?: [])
    } catch (Exception e) {
        // Fallback: extract unique types from existing fields
        def fields = cfManager.customFieldObjects
        def typeMap = [:]
        fields.each { cf ->
            def t = cf.customFieldType
            if (t && !typeMap.containsKey(t.key)) {
                typeMap[t.key] = [key: t.key, name: t.name, description: t.description ?: ""]
            }
        }
        ok(typeMap.values().sort { it.name })
    }
}


// ============================================================================
//  WORKFLOWS
// ============================================================================

def listWorkflows(String search) {
    def wfManager = ComponentAccessor.workflowManager
    def workflows = wfManager.workflows
    if (search) workflows = workflows.findAll { it.name.toLowerCase().contains(search.toLowerCase()) }
    def activeNames = wfManager.activeWorkflows*.name as Set

    ok(workflows.collect { JiraWorkflow wf ->
        [name: wf.name, description: wf.description ?: "", isDefault: wf.isDefault(),
         isActive: activeNames.contains(wf.name), stepsCount: wf.descriptor?.steps?.size() ?: 0,
         updatedDate: wf.updatedDate?.toString() ?: ""]
    }.sort { it.name })
}

def getWorkflow(String workflowName) {
    def wf = ComponentAccessor.workflowManager.getWorkflow(workflowName)
    if (!wf) return notFound("Workflow not found: ${workflowName}")
    def descriptor = wf.descriptor

    def steps = descriptor.steps.collect { StepDescriptor step ->
        def s = wf.getLinkedStatusObject(step)
        [id: step.id, name: step.name, status: s ? [id: s.id, name: s.name, category: s.statusCategory?.name] : null]
    }

    def initialActions = descriptor.initialActions?.collect { buildTransitionSummary(it, descriptor) } ?: []
    def globalActions = descriptor.globalActions?.collect { buildTransitionSummary(it, descriptor) } ?: []
    def transitions = []
    descriptor.steps.each { StepDescriptor step ->
        step.actions.each { transitions << buildTransitionSummary(it, descriptor, step.id) }
    }

    ok([name: wf.name, description: wf.description ?: "", isDefault: wf.isDefault(),
        steps: steps, initialActions: initialActions, globalActions: globalActions, transitions: transitions])
}

def buildTransitionSummary(ActionDescriptor action, WorkflowDescriptor descriptor, Integer fromStepId = null) {
    def toStepId = action.unconditionalResult?.step ?: 0
    def toStepName = toStepId > 0 ? (descriptor.steps.find { it.id == toStepId }?.name ?: "") : ""
    [id: action.id, name: action.name, fromStepId: fromStepId, toStepId: toStepId, toStepName: toStepName,
     hasConditions: action.restriction?.conditionsDescriptor != null,
     validatorsCount: action.validators?.size() ?: 0,
     postFunctionsCount: action.unconditionalResult?.postFunctions?.size() ?: 0]
}

def getWorkflowTransition(String workflowName, String transitionId) {
    def wf = ComponentAccessor.workflowManager.getWorkflow(workflowName)
    if (!wf) return notFound("Workflow not found: ${workflowName}")
    def action = wf.descriptor.getAction(transitionId as int)
    if (!action) return notFound("Transition not found: ${transitionId}")

    def conditions = action.restriction?.conditionsDescriptor ? serializeConditions(action.restriction.conditionsDescriptor) : null

    def extractFn = { f -> [type: f.type, className: f.args?.get("class.name") ?: f.args?.get("className") ?: "",
         args: f.args?.findAll { it.key != "class.name" && it.key != "className" } ?: [:]] }

    ok([id: action.id, name: action.name, conditions: conditions,
        validators: action.validators?.collect(extractFn) ?: [],
        preFunctions: action.preFunctions?.collect(extractFn) ?: [],
        postFunctions: action.unconditionalResult?.postFunctions?.collect(extractFn) ?: [],
        properties: action.metaAttributes ?: [:]])
}

def serializeConditions(ConditionsDescriptor cd) {
    [type: cd.type == 1 ? "AND" : "OR",
     conditions: cd.conditions?.collect { desc ->
         if (desc instanceof ConditionsDescriptor) return serializeConditions(desc)
         if (desc instanceof ConditionDescriptor)
             return [className: desc.args?.get("class.name") ?: "", args: desc.args?.findAll { it.key != "class.name" } ?: [:]]
     } ?: []]
}

def getWorkflowXml(String workflowName) {
    def wf = ComponentAccessor.workflowManager.getWorkflow(workflowName)
    if (!wf) return notFound("Workflow not found: ${workflowName}")
    try {
        def xml = null

        // Approach 1: descriptor.asXML() — available in some versions
        try { xml = wf.descriptor.asXML() } catch (Exception ignore) {}

        // Approach 2: writeXML with PrintWriter
        if (!xml) {
            try {
                def sw = new StringWriter()
                wf.descriptor.writeXML(new PrintWriter(sw), true)
                xml = sw.toString()
            } catch (Exception ignore) {}
        }
        if (!xml) {
            try {
                def sw = new StringWriter()
                wf.descriptor.writeXML(new PrintWriter(sw))
                xml = sw.toString()
            } catch (Exception ignore) {}
        }

        // Approach 3: WorkflowLoader static methods
        if (!xml) {
            try {
                def sw = new StringWriter()
                WorkflowLoader.writeXML(wf.descriptor, sw)
                xml = sw.toString()
            } catch (Exception ignore) {}
        }

        // Approach 4: Manual XML serialization via WorkflowManager
        if (!xml) {
            try {
                def wfManager = ComponentAccessor.workflowManager
                // getWorkflowXml returns the raw XML string in some DC versions
                xml = wfManager.getWorkflowAsXml(wf) ?: wfManager.getWorkflowXml(wf)
            } catch (Exception ignore) {}
        }

        // Approach 5: Read from DB via OfBiz (workflows stored as XML in jiraworkflows table)
        if (!xml) {
            try {
                def ofBiz = ComponentAccessor.ofBizDelegator
                def gvs = ofBiz.findByAnd("JiraWorkflows", [workflowname: workflowName])
                if (gvs) xml = gvs.first().getString("descriptor")
            } catch (Exception ignore) {}
        }

        if (xml) {
            return ok([name: wf.name, xml: xml])
        }

        return ok([name: wf.name, error: "XML export unavailable — all 5 methods failed",
                   hint: "Use get_workflow + get_workflow_transition instead"])
    } catch (Exception e) {
        return ok([name: wf.name, error: "XML export failed: ${e.message}",
                   hint: "Use get_workflow + get_workflow_transition instead"])
    }
}


// ============================================================================
//  SCREENS
// ============================================================================

def listScreens(String search) {
    def screens = ComponentAccessor.fieldScreenManager.fieldScreens
    if (search) screens = screens.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }
    ok(screens.collect { [id: it.id, name: it.name ?: "", description: it.description ?: "", tabsCount: it.tabs?.size() ?: 0] }.sort { it.name })
}

def getScreen(String screenId) {
    def screen = ComponentAccessor.fieldScreenManager.getFieldScreen(screenId as Long)
    if (!screen) return notFound("Screen not found: ${screenId}")
    def fieldManager = ComponentAccessor.fieldManager

    ok([id: screen.id, name: screen.name, description: screen.description ?: "",
        tabs: screen.tabs.collect { FieldScreenTab tab ->
            [id: tab.id, name: tab.name, position: tab.position,
             fields: tab.fieldScreenLayoutItems.collect { item ->
                 def fn = item.fieldId
                 try { fn = fieldManager.getField(item.fieldId)?.name ?: item.fieldId } catch (e) {}
                 [fieldId: item.fieldId, fieldName: fn, position: item.position]
             }.sort { it.position }]
        }.sort { it.position }])
}

def listScreenSchemes(String search) {
    def ssManager = ComponentAccessor.getComponent(FieldScreenSchemeManager)
    def schemes = ssManager.fieldScreenSchemes
    if (search) schemes = schemes.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }

    ok(schemes.collect { FieldScreenScheme scheme ->
        def mappings = []
        try {
            def defaultItem = scheme.getFieldScreenSchemeItem(null)
            if (defaultItem?.fieldScreen)
                mappings << [operation: "Default", screenId: defaultItem.fieldScreen.id, screenName: defaultItem.fieldScreen.name]
        } catch (Exception e) {}

        // Per-operation via IssueOperations (10.x safe)
        try {
            def ops = com.atlassian.jira.issue.operation.IssueOperations
            [[ops.CREATE_ISSUE_OPERATION, "Create"], [ops.EDIT_ISSUE_OPERATION, "Edit"], [ops.VIEW_ISSUE_OPERATION, "View"]].each { entry ->
                def item = scheme.getFieldScreenSchemeItem(entry[0])
                if (item?.fieldScreen)
                    mappings << [operation: entry[1], screenId: item.fieldScreen.id, screenName: item.fieldScreen.name]
            }
        } catch (Exception e) {}

        [id: scheme.id, name: scheme.name, description: scheme.description ?: "", mappings: mappings]
    }.sort { it.name })
}

def listIssueTypeScreenSchemes(String search) {
    def itssManager = ComponentAccessor.getComponent(IssueTypeScreenSchemeManager)
    def schemes = itssManager.issueTypeScreenSchemes
    if (search) schemes = schemes.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }
    def itManager = ComponentAccessor.getComponent(IssueTypeManager)

    ok(schemes.collect { IssueTypeScreenScheme itss ->
        [id: itss.id, name: itss.name, description: itss.description ?: "",
         mappings: (itss.entities?.collect { entity ->
             def itId = entity.issueTypeId
             def itName = "Default"
             if (itId) { try { itName = itManager.getIssueType(itId)?.name ?: itId } catch (e) { itName = itId } }
             [issueTypeId: itId ?: "default", issueTypeName: itName,
              screenSchemeId: entity.fieldScreenScheme?.id, screenSchemeName: entity.fieldScreenScheme?.name]
         } ?: [])]
    }.sort { it.name })
}


// ============================================================================
//  PERMISSION SCHEMES
// ============================================================================

def listPermissionSchemes() {
    def psManager = ComponentAccessor.permissionSchemeManager
    ok(psManager.schemeObjects.collect { scheme ->
        def projects = psManager.getProjects(scheme)
        [id: scheme.id, name: scheme.name, description: scheme.description ?: "",
         projectCount: projects?.size() ?: 0, projectKeys: projects?.collect { it.key }?.sort() ?: []]
    }.sort { it.name })
}

def getPermissionScheme(String schemeId) {
    def psManager = ComponentAccessor.permissionSchemeManager
    def scheme = psManager.schemeObjects.find { it.id == schemeId as Long }
    if (!scheme) return notFound("Permission scheme not found: ${schemeId}")

    def permissions = []
    try {
        def gv = psManager.getScheme(scheme.id)  // Scheme → GenericValue
        permissions = psManager.getEntities(gv)?.collect { e ->
            [permissionKey: e.getString("permission_key") ?: e.entityTypeId?.toString() ?: "",
             type: e.getString("type") ?: e.type ?: "",
             parameter: e.getString("parameter") ?: e.parameter ?: ""]
        }?.sort { it.permissionKey } ?: []
    } catch (Exception e) {
        try {
            // 10.x fallback via getPermissionSchemeEntries
            psManager.getPermissionSchemeEntries(scheme.id)?.each { entry ->
                permissions << [permissionKey: entry.key?.permissionKey() ?: "", type: entry.value?.type ?: "", parameter: entry.value?.parameter ?: ""]
            }
        } catch (Exception e2) {
            permissions = [[error: "Could not read entries: ${e2.message}"]]
        }
    }
    ok([id: scheme.id, name: scheme.name, description: scheme.description ?: "", permissions: permissions])
}


// ============================================================================
//  NOTIFICATION SCHEMES
// ============================================================================

def listNotificationSchemes() {
    def nsManager = ComponentAccessor.getComponent(NotificationSchemeManager)
    ok(nsManager.schemeObjects.collect { scheme ->
        def projects = nsManager.getProjects(scheme)
        [id: scheme.id, name: scheme.name, description: scheme.description ?: "",
         projectCount: projects?.size() ?: 0, projectKeys: projects?.collect { it.key }?.sort() ?: []]
    }.sort { it.name })
}

def getNotificationScheme(String schemeId) {
    def nsManager = ComponentAccessor.getComponent(NotificationSchemeManager)
    def scheme = nsManager.schemeObjects.find { it.id == schemeId as Long }
    if (!scheme) return notFound("Notification scheme not found: ${schemeId}")

    def notifications = []
    try {
        def gv = nsManager.getScheme(scheme.id)  // Scheme → GenericValue
        notifications = nsManager.getEntities(gv)?.collect { e ->
            [eventTypeId: e.getString("eventTypeId") ?: e.entityTypeId?.toString() ?: "",
             type: e.getString("type") ?: e.type ?: "",
             parameter: e.getString("parameter") ?: e.parameter ?: ""]
        }?.sort { it.eventTypeId } ?: []
    } catch (Exception e) {
        notifications = [[error: "Could not read entries: ${e.message}"]]
    }
    ok([id: scheme.id, name: scheme.name, description: scheme.description ?: "", notifications: notifications])
}


// ============================================================================
//  WORKFLOW SCHEMES — tries AssignableWorkflowScheme (10.x), falls back to legacy
// ============================================================================

def listWorkflowSchemes() {
    def wsManager = ComponentAccessor.workflowSchemeManager
    ok(wsManager.schemeObjects.collect { scheme ->
        def projects = wsManager.getProjects(scheme)
        [id: scheme.id, name: scheme.name, description: scheme.description ?: "",
         projectCount: projects?.size() ?: 0, projectKeys: projects?.collect { it.key }?.sort() ?: []]
    }.sort { it.name })
}

def getWorkflowScheme(String schemeId) {
    def wsManager = ComponentAccessor.workflowSchemeManager
    def itManager = ComponentAccessor.getComponent(IssueTypeManager)

    // Modern API (10.x): AssignableWorkflowScheme
    try {
        def aws = wsManager.getWorkflowSchemeObj(schemeId as Long)
        if (aws) {
            def mappings = aws.mappings.collect { m ->
                def itId = m.issueTypeId
                def itName = "Default"
                if (itId) { try { itName = itManager.getIssueType(itId)?.name ?: itId } catch (ex) {} }
                [issueTypeId: itId ?: "default", issueTypeName: itName, workflowName: m.workflow ?: ""]
            }.sort { it.issueTypeName }
            return ok([id: aws.id, name: aws.name, description: aws.description ?: "",
                       defaultWorkflow: aws.configuredDefaultWorkflow ?: "jira", mappings: mappings])
        }
    } catch (Exception e) {}

    // Legacy fallback — convert Scheme → GenericValue for getEntities()
    def scheme = wsManager.schemeObjects.find { it.id == schemeId as Long }
    if (!scheme) return notFound("Workflow scheme not found: ${schemeId}")

    def mappings = []
    def defaultWf = "jira"
    try {
        def gv = wsManager.getScheme(scheme.id)  // GenericValue
        mappings = wsManager.getEntities(gv)?.collect { e ->
            def itId = e.getString("issuetype") ?: e.entityTypeId?.toString()
            def itName = "Default"
            if (itId && itId != "0") { try { itName = itManager.getIssueType(itId)?.name ?: itId } catch (ex) {} }
            [issueTypeId: itId ?: "0", issueTypeName: itName, workflowName: e.getString("workflow") ?: e.parameter ?: ""]
        }?.sort { it.issueTypeName } ?: []
        defaultWf = wsManager.getDefaultWorkflow(scheme) ?: "jira"
    } catch (Exception e) {
        mappings = [[error: "Could not read entries: ${e.message}"]]
    }
    ok([id: scheme.id, name: scheme.name, description: scheme.description ?: "",
        defaultWorkflow: defaultWf, mappings: mappings])
}


// ============================================================================
//  PROJECTS — safe reverse lookup (no GenericValue)
// ============================================================================

def listProjects(String search) {
    def projectManager = ComponentAccessor.projectManager
    def projects = projectManager.projects
    if (search) {
        def s = search.toLowerCase()
        projects = projects.findAll { it.name.toLowerCase().contains(s) || it.key.toLowerCase().contains(s) }
    }

    def psManager = ComponentAccessor.permissionSchemeManager
    def wsManager = ComponentAccessor.workflowSchemeManager

    // Reverse lookup: scheme → projects (avoids deprecated getSchemes(project))
    def permMap = [:]; psManager.schemeObjects.each { s -> psManager.getProjects(s)?.each { p -> permMap[p.id] = s } }
    def wfMap = [:]; wsManager.schemeObjects.each { s -> wsManager.getProjects(s)?.each { p -> wfMap[p.id] = s } }

    ok(projects.collect { Project project ->
        [id: project.id, key: project.key, name: project.name,
         lead: project.getProjectLead()?.displayName ?: "",
         projectType: project.projectTypeKey?.key ?: "software",
         category: project.projectCategory?.name ?: "",
         permissionScheme: schemeInfo(permMap[project.id]),
         workflowScheme: schemeInfo(wfMap[project.id])]
    }.sort { it.key })
}

def getProjectConfig(String projectKey) {
    def project = ComponentAccessor.projectManager.getProjectObjByKey(projectKey.toUpperCase())
    if (!project) return notFound("Project not found: ${projectKey}")

    def psManager = ComponentAccessor.permissionSchemeManager
    def nsManager = ComponentAccessor.getComponent(NotificationSchemeManager)
    def wsManager = ComponentAccessor.workflowSchemeManager
    def itssManager = ComponentAccessor.getComponent(IssueTypeScreenSchemeManager)
    def flManager = ComponentAccessor.getComponent(FieldLayoutManager)
    def roleManager = ComponentAccessor.getComponent(ProjectRoleManager)

    // Safe reverse lookups
    def permScheme = findSchemeForProject(psManager, project)
    def notifScheme = findSchemeForProject(nsManager, project)
    def wfScheme = findSchemeForProject(wsManager, project)

    // Direct typed lookups (safe in 10.x)
    def itss = itssManager.getIssueTypeScreenScheme(project)
    def flScheme = flManager.getFieldConfigurationScheme(project)
    def itsScheme = ComponentAccessor.issueTypeSchemeManager.getConfigScheme(project)

    def roles = []
    try {
        roles = roleManager.getProjectRoles()?.collect { role ->
            def actors = roleManager.getProjectRoleActors(role, project)
            def members = actors?.roleActors?.collectMany { ra ->
                if (ra.type == "atlassian-group-role-actor") return [[type: "group", value: ra.parameter]]
                return ra.users?.collect { u -> [type: "user", key: u.key, name: u.displayName] } ?: []
            } ?: []
            [id: role.id, name: role.name, members: members]
        } ?: []
    } catch (Exception e) { roles = [[error: e.message]] }

    def components = ComponentAccessor.projectComponentManager
        .findAllForProject(project.id)?.collect { [id: it.id, name: it.name, lead: it.componentLead?.displayName ?: ""] } ?: []

    def versions = ComponentAccessor.versionManager.getVersions(project.id)?.collect {
        [id: it.id, name: it.name, released: it.released, archived: it.archived,
         startDate: it.startDate?.toString() ?: "", releaseDate: it.releaseDate?.toString() ?: ""]
    } ?: []

    ok([id: project.id, key: project.key, name: project.name, description: project.description ?: "",
        lead: project.getProjectLead()?.displayName ?: "",
        projectType: project.projectTypeKey?.key ?: "software", category: project.projectCategory?.name ?: "",
        permissionScheme: schemeInfo(permScheme), notificationScheme: schemeInfo(notifScheme),
        workflowScheme: schemeInfo(wfScheme),
        issueTypeScheme: itsScheme ? [id: itsScheme.id, name: itsScheme.name] : null,
        issueTypeScreenScheme: itss ? [id: itss.id, name: itss.name] : null,
        fieldConfigurationScheme: flScheme ? [id: flScheme.id, name: flScheme.name] : null,
        roles: roles, components: components, versions: versions])
}


// ============================================================================
//  USERS & GROUPS — with 10.x pagination safety
// ============================================================================

def listGroups(String search) {
    def groupManager = ComponentAccessor.groupManager
    def groups = groupManager.allGroups
    if (search) groups = groups.findAll { it.name.toLowerCase().contains(search.toLowerCase()) }

    ok(groups.collect { group ->
        def count = 0
        try { count = groupManager.getUsersInGroup(group)?.size() ?: 0 } catch (e) { count = -1 }
        [name: group.name, memberCount: count]
    }.sort { it.name })
}

def getGroupMembers(String groupName) {
    def groupManager = ComponentAccessor.groupManager
    def group = groupManager.getGroup(groupName)
    if (!group) return notFound("Group not found: ${groupName}")

    def members = []
    try {
        members = groupManager.getUsersInGroup(group)?.collect {
            [key: it.key, username: it.name, displayName: it.displayName, email: it.emailAddress ?: "", active: it.isActive()]
        }?.sort { it.displayName } ?: []
    } catch (Exception e) { members = [[error: e.message]] }

    // 10.x may cap results at 100
    def truncated = members.size() == 100
    ok([group: groupName, count: members.size(), truncated: truncated,
        truncatedHint: truncated ? "Jira 10.x may cap at 100. Use admin UI for full list." : null,
        members: members])
}

def listProjectRoles() {
    def roleManager = ComponentAccessor.getComponent(ProjectRoleManager)
    ok(roleManager.projectRoles?.collect { [id: it.id, name: it.name, description: it.description ?: ""] }?.sort { it.name } ?: [])
}

def getProjectRoleMembers(String projectKey, String roleId) {
    def project = ComponentAccessor.projectManager.getProjectObjByKey(projectKey.toUpperCase())
    if (!project) return notFound("Project not found: ${projectKey}")
    def roleManager = ComponentAccessor.getComponent(ProjectRoleManager)
    def role = roleManager.getProjectRole(roleId as Long)
    if (!role) return notFound("Role not found: ${roleId}")

    def members = []
    roleManager.getProjectRoleActors(role, project)?.roleActors?.each { ra ->
        if (ra.type == "atlassian-group-role-actor") members << [type: "group", value: ra.parameter]
        ra.users?.each { u -> members << [type: "user", key: u.key, username: u.name, displayName: u.displayName] }
    }
    ok([project: projectKey, role: [id: role.id, name: role.name], members: members])
}

def getUser(String username, String key) {
    if (!username && !key) return ok([error: "Provide 'username' or 'key' parameter"])

    def userManager = ComponentAccessor.userManager
    def user = null

    if (key) {
        user = userManager.getUserByKey(key)
    }
    if (!user && username) {
        user = userManager.getUserByName(username)
    }
    if (!user) return notFound("User not found: ${username ?: key}")

    def groupManager = ComponentAccessor.groupManager
    def groups = groupManager.getGroupNamesForUser(user)?.sort() ?: []

    // Application access
    def appRoles = []
    try {
        def appRoleManager = ComponentAccessor.getComponent(
            com.atlassian.jira.application.ApplicationRoleManager)
        appRoles = appRoleManager.getRolesForUser(user)?.collect { it.key?.toString() } ?: []
    } catch (Exception e) {}

    ok([
        key        : user.key,
        username   : user.name,
        displayName: user.displayName,
        email      : user.emailAddress ?: "",
        active     : user.isActive(),
        groups     : groups,
        applicationRoles: appRoles
    ])
}

def listApplicationRoles() {
    try {
        def appRoleManager = ComponentAccessor.getComponent(
            com.atlassian.jira.application.ApplicationRoleManager)
        def allRoles = appRoleManager.roles

        ok(allRoles?.collect { role ->
            def groups = role.groups?.collect { it.name }?.sort() ?: []
            def defaultGroups = role.defaultGroups?.collect { it.name }?.sort() ?: []
            def userCount = 0
            try { userCount = appRoleManager.getUserCount(role.key) } catch (e) {}
            def seats = 0
            try { seats = role.numberOfSeats ?: 0 } catch (Exception ignored) {}
            def remainingSeats = 0
            try { remainingSeats = seats > 0 ? seats - userCount : -1 } catch (e) {}

            [key: role.key?.toString() ?: "",
             name: role.name ?: "",
             groups: groups,
             defaultGroups: defaultGroups,
             userCount: userCount,
             numberOfSeats: seats,
             remainingSeats: remainingSeats]
        }?.sort { it.name } ?: [])
    } catch (Exception e) {
        // Fallback: use REST-like approach via ApplicationAuthorizationService
        try {
            def authService = ComponentAccessor.getComponent(
                com.atlassian.jira.application.ApplicationAuthorizationService)
            def keys = ["jira-software", "jira-servicedesk", "jira-core"]
            ok(keys.collect { keyStr ->
                def appKey = com.atlassian.jira.application.ApplicationKeys.valueOf(keyStr.toUpperCase().replace("-", "_"))
                def count = 0
                try { count = authService.getUserCount(appKey) } catch (ex) {}
                [key: keyStr, userCount: count]
            })
        } catch (Exception e2) {
            ok([error: "Could not read application roles: ${e.message}"])
        }
    }
}


// ============================================================================
//  ISSUE TYPES
// ============================================================================

def listIssueTypes() {
    ok(ComponentAccessor.getComponent(IssueTypeManager).issueTypes.collect { IssueType it ->
        [id: it.id, name: it.name, description: it.description ?: "", isSubtask: it.isSubTask(), iconUrl: it.iconUrl ?: ""]
    }.sort { it.name })
}

def listIssueTypeSchemes(String search) {
    def itsManager = ComponentAccessor.issueTypeSchemeManager
    def schemeMap = [:]
    ComponentAccessor.projectManager.projects.each { project ->
        try {
            def scheme = itsManager.getConfigScheme(project)
            if (scheme) {
                if (!schemeMap.containsKey(scheme.id)) schemeMap[scheme.id] = [scheme: scheme, projects: []]
                schemeMap[scheme.id].projects << project.key
            }
        } catch (Exception e) {
            // skip project with broken scheme config
        }
    }

    ok(schemeMap.values().collect { entry ->
        try {
            def scheme = entry.scheme
            if (search && !scheme.name?.toLowerCase()?.contains(search.toLowerCase())) return null
            def issueTypes = []
            try { issueTypes = itsManager.getIssueTypesForConfigScheme(scheme)?.collect { [id: it.id, name: it.name] } ?: [] } catch (Exception ignore) {}
            def defaultIT = null
            try { defaultIT = itsManager.getDefaultIssueType(scheme) } catch (Exception ignore) {}
            [id: scheme.id, name: scheme.name ?: "", description: scheme.description ?: "",
             defaultIssueType: defaultIT ? [id: defaultIT.id, name: defaultIT.name] : null,
             issueTypes: issueTypes, projectKeys: entry.projects.sort()]
        } catch (Exception e) {
            return null
        }
    }.findAll { it != null }.sort { it.name })
}

def listReferenceData() {
    ok([
        statuses: ComponentAccessor.getComponent(StatusManager).statuses?.collect {
            [id: it.id, name: it.name, description: it.description ?: "",
             category: it.statusCategory?.name ?: "", categoryKey: it.statusCategory?.key ?: ""]
        }?.sort { it.name } ?: [],
        priorities: ComponentAccessor.getComponent(PriorityManager).priorities?.collect {
            [id: it.id, name: it.name, description: it.description ?: "", sequence: it.sequence]
        }?.sort { it.sequence } ?: [],
        resolutions: ComponentAccessor.getComponent(ResolutionManager).resolutions?.collect {
            [id: it.id, name: it.name, description: it.description ?: "", sequence: it.sequence]
        }?.sort { it.sequence } ?: []
    ])
}


// ============================================================================
//  FIELD CONFIGURATIONS
// ============================================================================

def listFieldConfigurations(String search) {
    def flManager = ComponentAccessor.getComponent(FieldLayoutManager)
    def layouts = flManager.editableFieldLayouts
    if (search) layouts = layouts.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }

    ok(layouts.collect { FieldLayout layout ->
        [id: layout.id, name: layout.name ?: "Default Field Configuration",
         description: layout.description ?: "", isDefault: layout.isDefault(),
         fieldCount: layout.fieldLayoutItems?.size() ?: 0]
    }.sort { it.name })
}

def getFieldConfiguration(String configId) {
    def flManager = ComponentAccessor.getComponent(FieldLayoutManager)
    def layout = (configId == "default" || configId == "0")
        ? flManager.editableDefaultFieldLayout
        : flManager.editableFieldLayouts.find { it.id == configId as Long }
    if (!layout) return notFound("Field configuration not found: ${configId}")

    ok([id: layout.id, name: layout.name ?: "Default Field Configuration",
        description: layout.description ?: "", isDefault: layout.isDefault(),
        fields: layout.fieldLayoutItems?.collect { FieldLayoutItem item ->
            [fieldId: item.orderableField?.id ?: "", fieldName: item.orderableField?.name ?: "",
             isHidden: item.isHidden(), isRequired: item.isRequired(),
             rendererType: item.rendererType ?: "", description: item.fieldDescription ?: ""]
        }?.sort { it.fieldName } ?: []])
}

def listFieldConfigSchemes(String search) {
    def flManager = ComponentAccessor.getComponent(FieldLayoutManager)
    def schemes = flManager.fieldLayoutSchemes
    if (search) schemes = schemes.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }

    ok(schemes.collect { FieldLayoutScheme scheme ->
        def projects = flManager.getProjects(scheme)
        [id: scheme.id, name: scheme.name, description: scheme.description ?: "",
         projectCount: projects?.size() ?: 0, projectKeys: projects?.collect { it.key }?.sort() ?: []]
    }.sort { it.name })
}

def getFieldConfigScheme(String schemeId) {
    def flManager = ComponentAccessor.getComponent(FieldLayoutManager)
    def itManager = ComponentAccessor.getComponent(IssueTypeManager)
    def scheme = flManager.fieldLayoutSchemes.find { it.id == schemeId as Long }
    if (!scheme) return notFound("Field config scheme not found: ${schemeId}")

    def mappings = []
    try {
        scheme.entities?.each { FieldLayoutSchemeEntity entity ->
            try {
                def itId = entity.issueTypeId
                def itName = "Default"
                if (itId) { try { itName = itManager.getIssueType(itId)?.name ?: itId } catch (e) { itName = itId } }
                def fcId = null
                def fcName = "Default Field Configuration"
                try {
                    def fl = entity.fieldLayout
                    if (fl) { fcId = fl.id; fcName = fl.name ?: fcName }
                } catch (Exception ignore) {}
                mappings << [issueTypeId: itId ?: "default", issueTypeName: itName,
                             fieldConfigId: fcId, fieldConfigName: fcName]
            } catch (Exception e) {
                mappings << [issueTypeId: "unknown", issueTypeName: "Error: ${e.message}",
                             fieldConfigId: null, fieldConfigName: "Default Field Configuration"]
            }
        }
    } catch (Exception e) {
        return ok([id: scheme.id, name: scheme.name, description: scheme.description ?: "",
                   error: "Failed to read scheme entities: ${e.message}", mappings: []])
    }

    ok([id: scheme.id, name: scheme.name, description: scheme.description ?: "",
        mappings: mappings.sort { it.issueTypeName }])
}


// ============================================================================
//  ISSUE LINK TYPES
// ============================================================================

def listIssueLinkTypes() {
    def linkTypeManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.link.IssueLinkTypeManager)
    ok(linkTypeManager.issueLinkTypes?.collect {
        [id: it.id, name: it.name, inward: it.inward, outward: it.outward, style: it.style ?: ""]
    }?.sort { it.name } ?: [])
}


// ============================================================================
//  ISSUE SECURITY SCHEMES
// ============================================================================

def listIssueSecuritySchemes() {
    def issManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.security.IssueSecuritySchemeManager)
    ok(issManager.schemeObjects.collect { scheme ->
        def projects = issManager.getProjects(scheme)
        [id: scheme.id, name: scheme.name, description: scheme.description ?: "",
         projectCount: projects?.size() ?: 0, projectKeys: projects?.collect { it.key }?.sort() ?: []]
    }.sort { it.name })
}

def getIssueSecurityScheme(String schemeId) {
    def issManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.security.IssueSecuritySchemeManager)
    def scheme = issManager.schemeObjects.find { it.id == schemeId as Long }
    if (!scheme) return notFound("Issue security scheme not found: ${schemeId}")

    def levels = []
    try {
        def islManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.security.IssueSecurityLevelManager)
        def gv = issManager.getScheme(scheme.id)  // Scheme → GenericValue

        // Try multiple method names — API changed across Jira versions
        def securityLevels = null
        try {
            securityLevels = islManager.getIssueSecurityLevels(scheme.id)
        } catch (MissingMethodException ignore) {
            try {
                securityLevels = islManager.getSecurityLevelsForScheme(scheme.id)
            } catch (MissingMethodException ignore2) {
                try {
                    securityLevels = islManager.getAllSecurityLevelsForScheme(scheme.id)
                } catch (MissingMethodException ignore3) {
                    securityLevels = islManager.getSecurityLevels(scheme.id)
                }
            }
        }

        levels = securityLevels?.collect { level ->
            def entities = []
            try {
                // Try per-level entities lookup
                entities = issManager.getEntities(gv, level.id)?.collect { e ->
                    [type: e.getString("type") ?: e.type ?: "", parameter: e.getString("parameter") ?: e.parameter ?: ""]
                } ?: []
            } catch (Exception ignore) {
                try {
                    // Fallback: get all entities for scheme and filter by level
                    entities = issManager.getEntities(gv)?.findAll { e ->
                        (e.getString("security") ?: e.get("security"))?.toString() == level.id?.toString()
                    }?.collect { e ->
                        [type: e.getString("type") ?: e.type ?: "", parameter: e.getString("parameter") ?: e.parameter ?: ""]
                    } ?: []
                } catch (Exception ignore2) {
                    entities = []
                }
            }
            [id: level.id, name: level.name, description: level.description ?: "", entities: entities]
        } ?: []
    } catch (Exception e) {
        levels = [[error: "Could not read security levels: ${e.message}"]]
    }

    ok([id: scheme.id, name: scheme.name, description: scheme.description ?: "", levels: levels])
}


// ============================================================================
//  GLOBAL CONFIG & METADATA
// ============================================================================

def getServerInfo() {
    def props = ComponentAccessor.applicationProperties
    def buildUtils = ComponentAccessor.getComponent(com.atlassian.jira.util.BuildUtilsInfo)
    ok([
        version     : buildUtils?.version ?: "",
        buildNumber : buildUtils?.currentBuildNumber ?: "",
        buildDate   : buildUtils?.currentBuildDate ?: "",
        baseUrl     : props.getString("jira.baseurl") ?: "",
        title       : props.getString("jira.title") ?: "",
        mode        : props.getString("jira.mode") ?: ""
    ])
}

def getApplicationProperties(String search) {
    def props = ComponentAccessor.applicationProperties
    // Expose key admin-relevant properties
    def keys = [
        "jira.baseurl", "jira.title", "jira.mode",
        "jira.option.allowunassigned", "jira.option.voting", "jira.option.watching",
        "jira.option.allowsubtasks", "jira.option.allowtimetracking",
        "jira.timetracking.hours.per.day", "jira.timetracking.days.per.week",
        "jira.option.emailvisible", "jira.option.allowattachments",
        "jira.attachment.size", "jira.clone.prefix",
        "jira.date.picker.java.format", "jira.date.time.picker.java.format",
        "jira.lf.date.time.complete", "jira.lf.date.dmy",
        "jira.search.views.default.max", "jira.table.cols.subtasks",
        "jira.projectkey.pattern", "jira.issue.editable",
        "jira.option.user.externalmgt", "jira.option.rpc.allow",
        "jira.i18n.default.locale"
    ]

    def result = keys.collect { key ->
        def val = null
        try { val = props.getString(key) } catch (e) {}
        if (val == null) try { val = props.getDefaultBackedString(key) } catch (e) {}
        [key: key, value: val ?: ""]
    }

    if (search) result = result.findAll { it.key.toLowerCase().contains(search.toLowerCase()) || it.value?.toLowerCase()?.contains(search.toLowerCase()) }

    ok(result)
}

def listProjectCategories() {
    ok(ComponentAccessor.projectManager.allProjectCategories?.collect {
        [id: it.id, name: it.name, description: it.description ?: ""]
    }?.sort { it.name } ?: [])
}

def listEventTypes() {
    def etManager = ComponentAccessor.getComponent(com.atlassian.jira.event.type.EventTypeManager)
    ok(etManager.eventTypes?.collect {
        [id: it.id, name: it.name, description: it.description ?: "", isSystem: it.isSystemEventType()]
    }?.sort { it.name } ?: [])
}

def listGlobalPermissions() {
    def gpManager = ComponentAccessor.getComponent(com.atlassian.jira.security.GlobalPermissionManager)
    def gpTypes = ComponentAccessor.getComponent(com.atlassian.jira.permission.GlobalPermissionType.class) // may not work
    def result = []

    try {
        // Get all global permission keys and who has them
        def allPerms = gpManager.allGlobalPermissions
        result = allPerms?.collect { perm ->
            def groups = gpManager.getGroupNames(perm) ?: []
            [key: perm.globalPermissionKey ?: perm.toString(), groups: groups.sort()]
        }?.sort { it.key } ?: []
    } catch (Exception e) {
        // Fallback: use known permission keys
        def knownKeys = [
            "SYSTEM_ADMIN", "ADMINISTER", "USE", "USER_PICKER",
            "CREATE_SHARED_OBJECTS", "MANAGE_GROUP_FILTER_SUBSCRIPTIONS", "BULK_CHANGE"
        ]
        result = knownKeys.collect { key ->
            try {
                def groups = gpManager.getGroupsWithPermission(com.atlassian.jira.permission.GlobalPermissionKey.of(key))
                [key: key, groups: groups?.collect { it.name }?.sort() ?: []]
            } catch (Exception ex) {
                [key: key, groups: [], error: ex.message]
            }
        }
    }

    ok(result)
}


// ============================================================================
//  SHARED FILTERS & DASHBOARDS
// ============================================================================

def listSharedFilters(String search) {
    try {
        def user = ComponentAccessor.jiraAuthenticationContext.loggedInUser
        def searchService = ComponentAccessor.getComponent(com.atlassian.jira.bc.filter.SearchRequestService)
        def filters = []

        // Try multiple approaches for Jira 10.x compatibility
        try {
            // getOwnedFilters returns filters owned by user
            filters = searchService.getOwnedFilters(user) ?: []
        } catch (Exception e1) {
            try {
                // getFavouriteFilters as fallback
                filters = searchService.getFavouriteFilters(user) ?: []
            } catch (Exception e2) {
                try {
                    // Direct manager approach
                    def srManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.search.SearchRequestManager)
                    filters = srManager.getAllOwnedSearchRequests(user) ?: []
                } catch (Exception e3) {
                    return ok([error: "Could not retrieve filters. Tried: getOwnedFilters (${e1.message}), getFavouriteFilters (${e2.message}), getAllOwnedSearchRequests (${e3.message})"])
                }
            }
        }

        if (search) filters = filters.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }

        ok(filters.collect {
            [id: it.id, name: it.name, description: it.description ?: "",
             jql: it.query?.queryString ?: "",
             owner: it.ownerUserName ?: it.owner?.key ?: "",
             favouriteCount: it.favouriteCount ?: 0]
        }.sort { it.name })
    } catch (Exception e) {
        ok([error: "Failed to list shared filters: ${e.message}"])
    }
}

def listDashboards(String search) {
    try {
        def ppManager = ComponentAccessor.getComponent(com.atlassian.jira.portal.PortalPageManager)
        def user = ComponentAccessor.jiraAuthenticationContext.loggedInUser
        def dashboards = []

        try {
            // getSharedPortalPages requires user in 10.x
            dashboards = ppManager.getSharedPortalPages(user) ?: []
        } catch (Exception e1) {
            try {
                dashboards = ppManager.getAllOwnedPortalPages(user) ?: []
            } catch (Exception e2) {
                try {
                    // Try system default only
                    def sysDash = ppManager.getSystemDefaultPortalPage()
                    dashboards = sysDash ? [sysDash] : []
                } catch (Exception e3) {
                    return ok([error: "Could not retrieve dashboards. Tried: getSharedPortalPages (${e1.message}), getAllOwnedPortalPages (${e2.message})"])
                }
            }
        }

        if (search) dashboards = dashboards.findAll { it.name?.toLowerCase()?.contains(search.toLowerCase()) }

        ok(dashboards.collect {
            def isSysDefault = false
            try { isSysDefault = it.isSystemDefaultPortalPage() } catch (Exception ignore) {}
            [id: it.id, name: it.name, description: it.description ?: "",
             owner: it.ownerUserName ?: "",
             favouriteCount: it.favouriteCount ?: 0,
             systemDashboard: isSysDefault]
        }.sort { it.name })
    } catch (Exception e) {
        ok([error: "Failed to list dashboards: ${e.message}"])
    }
}


// ============================================================================
//  CLUSTER (DC)
// ============================================================================

def getClusterInfo() {
    try {
        def clusterManager = ComponentAccessor.getComponent(com.atlassian.jira.cluster.ClusterManager)
        def nodes = clusterManager.allNodes?.collect { node ->
            [
                nodeId   : node.nodeId,
                state    : node.state?.name() ?: "",
                isSelf   : node.isSelf(),
                cachePort: node.cacheListenerPort ?: 0,
                ip       : node.ip ?: ""
            ]
        } ?: []

        ok([
            isClustered: clusterManager.isClustered(),
            nodeCount  : nodes.size(),
            nodes      : nodes
        ])
    } catch (Exception e) {
        ok([isClustered: false, error: "Could not read cluster info: ${e.message}"])
    }
}


// ============================================================================
//  PRIORITY SCHEMES (10.x)
// ============================================================================

def listPrioritySchemes() {
    try {
        def psManager = ComponentAccessor.getComponent(
            Class.forName("com.atlassian.jira.issue.priority.PrioritySchemeManager"))

        if (!psManager) return ok([error: "PrioritySchemeManager not available"])

        def schemes = psManager.getAllSchemes()

        ok(schemes?.collect { scheme ->
            def priorities = []
            try {
                priorities = psManager.getPrioritiesForScheme(scheme.id)?.collect {
                    [id: it.id, name: it.name]
                } ?: []
            } catch (Exception e) {}

            def projects = []
            try {
                projects = psManager.getProjectsForScheme(scheme.id)?.collect { it.key }?.sort() ?: []
            } catch (Exception e) {}

            [id: scheme.id, name: scheme.name, description: scheme.description ?: "",
             isDefault: scheme.isDefault(),
             priorities: priorities, projectKeys: projects]
        }?.sort { it.name } ?: [])
    } catch (Exception e) {
        ok([error: "Priority Schemes not available: ${e.message}",
            hint: "Use list_reference_data for global priorities list."])
    }
}




// ============================================================================
//  ASSETS (Insight / CMDB) — via Java API (OSGi facades)
//  Direct Java API calls — no REST, no auth issues.
// ============================================================================

def getFacade(String simpleName) {
    try {
        return ComponentAccessor.getOSGiComponentInstanceOfType(
            Class.forName("com.riadalabs.jira.plugins.insight.channel.external.api.facade.${simpleName}"))
    } catch (Exception e) {
        return null
    }
}

// ---- Object Schemas ----

def listObjectSchemas() {
    try {
        def facade = getFacade("ObjectSchemaFacade")
        if (!facade) return ok([error: "Assets/Insight not installed", hint: "ObjectSchemaFacade not found via OSGi"])
        def schemas = facade.findObjectSchemaBeans()
        ok(schemas?.collect {
            def entry = [id: it.id, name: it.name, description: it.description ?: ""]
            try { entry.key = it.objectSchemaKey } catch (Exception ignore) {}
            try { entry.objectCount = it.objectCount } catch (Exception ignore) { entry.objectCount = -1 }
            entry
        }?.sort { it.name } ?: [])
    } catch (Exception e) {
        ok([error: "Assets not available: ${e.message}", hint: "Ensure Assets/Insight plugin is installed"])
    }
}

def getObjectSchema(String schemaId) {
    try {
        def schemaFacade = getFacade("ObjectSchemaFacade")
        def typeFacade = getFacade("ObjectTypeFacade")
        if (!schemaFacade) return ok([error: "Assets not installed"])
        def schema = schemaFacade.loadObjectSchemaBean(schemaId as int)
        if (!schema) return notFound("Object schema not found: ${schemaId}")
        def types = typeFacade?.findObjectTypeBeans(schemaId as int) ?: []
        def result = [id: schema.id, name: schema.name, description: schema.description ?: ""]
        try { result.key = schema.objectSchemaKey } catch (Exception ignore) {}
        result.objectTypes = types.collect { safeObjectType(it) }.sort { it.name }
        ok(result)
    } catch (Exception e) {
        ok([error: "Failed to get schema ${schemaId}: ${e.message}"])
    }
}

// Safe property reader for Asset beans — avoids NoSuchProperty errors
def safeObjectType(bean) {
    def r = [id: bean.id, name: bean.name]
    try { r.description = bean.description ?: "" } catch (Exception ignore) {}
    try { r.parentObjectTypeId = bean.parentObjectTypeId ?: 0 } catch (Exception ignore) {}
    try { r.objectCount = bean.objectCount ?: 0 } catch (Exception ignore) {}
    try { r.position = bean.position ?: 0 } catch (Exception ignore) {}
    try { r.inherited = bean.inherited ?: false } catch (Exception ignore) {}
    try { r.abstractType = bean.abstractObjectType ?: false } catch (Exception ignore) {}
    r
}

// ---- Object Types ----

def listObjectTypes(String schemaId) {
    try {
        def facade = getFacade("ObjectTypeFacade")
        if (!facade) return ok([error: "Assets not installed"])
        def types = facade.findObjectTypeBeans(schemaId as int) ?: []
        ok(types.collect { safeObjectType(it) }.sort { it.name })
    } catch (Exception e) {
        ok([error: "Failed to list object types: ${e.message}"])
    }
}

def getObjectTypeAttributes(String objectTypeId) {
    try {
        def facade = getFacade("ObjectTypeAttributeFacade")
        if (!facade) return ok([error: "Assets not installed"])
        def attrs = facade.findObjectTypeAttributeBeans(objectTypeId as int) ?: []
        ok(attrs.collect {
            def r = [id: it.id, name: it.name]
            try { r.typeName = it.defaultType?.name ?: it.type?.toString() ?: "" } catch (Exception ignore) {}
            try { r.description = it.description ?: "" } catch (Exception ignore) {}
            try { r.editable = it.editable != false } catch (Exception ignore) {}
            try { r.system = it.system ?: false } catch (Exception ignore) {}
            try { r.minimumCardinality = it.minimumCardinality ?: 0; r.required = r.minimumCardinality > 0 } catch (Exception ignore) {}
            try { r.maximumCardinality = it.maximumCardinality ?: -1 } catch (Exception ignore) {}
            try { r.hidden = it.hidden ?: false } catch (Exception ignore) {}
            try { r.uniqueAttribute = it.uniqueAttribute ?: false } catch (Exception ignore) {}
            try { r.referenceObjectTypeId = it.referenceObjectTypeId ?: 0 } catch (Exception ignore) {}
            try { r.referenceType = it.referenceType?.name ?: "" } catch (Exception ignore) {}
            try { r.position = it.position ?: 0 } catch (Exception ignore) {}
            r
        }.sort { it.position ?: 0 })
    } catch (Exception e) {
        ok([error: "Failed to get attributes: ${e.message}"])
    }
}

// ---- AQL Search ----

def aqlSearch(String schema, String aql, String maxResults) {
    if (!aql) return ok([error: "aql parameter is required. Example: objectType = Server"])
    def limit = maxResults ? Math.min(Math.max(maxResults as int, 1), 50) : 25
    try {
        def iqlFacade = getFacade("IQLFacade")
        if (!iqlFacade) return ok([error: "Assets not installed"])
        def objects = []
        try {
            // findObjects(int schemaId, String iql) or findObjects(String iql, int page, int perPage)
            if (schema) {
                objects = iqlFacade.findObjects(schema as int, aql)
            } else {
                objects = iqlFacade.findObjects(aql)
            }
        } catch (Exception e1) {
            try { objects = iqlFacade.findObjectsByIQL(aql) } catch (Exception e2) {
                return ok([error: "AQL search failed: ${e1.message}, fallback: ${e2.message}", aql: aql])
            }
        }
        ok([aql: aql, count: objects?.size() ?: 0,
            objects: (objects ?: []).take(limit).collect { obj ->
                [id: obj.id, key: obj.objectKey ?: "", label: obj.label ?: "",
                 objectTypeId: obj.objectTypeId ?: 0,
                 created: obj.created?.toString() ?: "", updated: obj.updated?.toString() ?: ""]
            }])
    } catch (Exception e) {
        ok([error: "AQL search failed: ${e.message}", aql: aql])
    }
}

// ---- Object Details ----

def getAssetObject(String objectId) {
    if (!objectId) return ok([error: "id parameter is required (numeric object ID)"])
    try {
        def objectFacade = getFacade("ObjectFacade")
        if (!objectFacade) return ok([error: "Assets not installed"])
        def obj = objectFacade.loadObjectBean(objectId as int)
        if (!obj) return notFound("Object not found: ${objectId}")
        def attrs = []
        try {
            def attrBeans = objectFacade.findObjectAttributeBeans(objectId as int) ?: []
            def otaFacade = getFacade("ObjectTypeAttributeFacade")
            attrs = attrBeans.collect { attr ->
                def otaBean = null
                try { otaBean = otaFacade?.loadObjectTypeAttributeBean(attr.objectTypeAttributeId) } catch (Exception ignore) {}
                [id: attr.id,
                 name: otaBean?.name ?: "attr_${attr.objectTypeAttributeId}",
                 type: otaBean?.defaultType?.name ?: "",
                 values: attr.objectAttributeValueBeans?.collect { val ->
                     def result = [value: val.value?.toString() ?: "", displayValue: val.displayValue ?: val.value?.toString() ?: ""]
                     if (val.referencedObjectBeanId) {
                         try {
                             def refObj = objectFacade.loadObjectBean(val.referencedObjectBeanId)
                             if (refObj) result.referencedObject = [id: refObj.id, key: refObj.objectKey ?: "", label: refObj.label ?: ""]
                         } catch (Exception ignore) {}
                     }
                     result
                 } ?: []]
            }
        } catch (Exception ignore) {}
        ok([id: obj.id, key: obj.objectKey ?: "", label: obj.label ?: "",
            objectType: [id: obj.objectTypeId],
            created: obj.created?.toString() ?: "", updated: obj.updated?.toString() ?: "",
            attributes: attrs])
    } catch (Exception e) {
        ok([error: "Failed to get object ${objectId}: ${e.message}"])
    }
}

// ---- Reference Types ----

def listReferenceTypes(String schemaId) {
    if (!schemaId) return ok([error: "schemaId parameter is required"])
    try {
        def facade = getFacade("ObjectSchemaPropertyFacade") ?: getFacade("ReferenceTypeFacade") ?: getFacade("ConfigureFacade")
        if (!facade) return ok([error: "ReferenceType facade not available. Tried: ObjectSchemaPropertyFacade, ReferenceTypeFacade, ConfigureFacade"])
        def types = facade.findReferenceTypeBeans(schemaId as int) ?: []
        ok(types.collect {
            [id: it.id, name: it.name, description: it.description ?: "",
             color: it.color ?: "", removable: it.removable ?: false]
        }.sort { it.name })
    } catch (Exception e) {
        ok([error: "Failed to list reference types: ${e.message}"])
    }
}

// ---- Status Types ----

def listStatusTypes(String schemaId) {
    if (!schemaId) return ok([error: "schemaId parameter is required"])
    try {
        def facade = getFacade("ObjectSchemaPropertyFacade") ?: getFacade("StatusTypeFacade") ?: getFacade("ConfigureFacade")
        if (!facade) return ok([error: "StatusType facade not available. Tried: ObjectSchemaPropertyFacade, StatusTypeFacade, ConfigureFacade"])
        def types = facade.findStatusTypeBeans(schemaId as int) ?: []
        ok(types.collect {
            def catName = [0: "Active", 1: "Inactive", 2: "Pending"].get(it.category, "Unknown")
            [id: it.id, name: it.name, description: it.description ?: "",
             category: it.category ?: 0, categoryName: catName]
        }.sort { it.name })
    } catch (Exception e) {
        ok([error: "Failed to list status types: ${e.message}"])
    }
}

// ---- Import Configurations ----

def listImportConfigs(String schemaId) {
    if (!schemaId) return ok([error: "schemaId parameter is required"])
    try {
        def facade = getFacade("ImportSourceConfigurationFacade")
        if (!facade) return ok([error: "Assets not installed or ImportSourceConfigurationFacade not available"])
        def configs = facade.findImportSourcesBySchema(schemaId as Integer) ?: []
        ok(configs.collect {
            def r = [id: it.id]
            try { r.name = it.name ?: "" } catch (Exception ignore) {}
            try { r.description = it.description ?: "" } catch (Exception ignore) {}
            try { r.type = it.type?.toString() ?: it.module ?: "" } catch (Exception ignore) {}
            try { r.enabled = it.enabled != false } catch (Exception ignore) {}
            try { r.cronExpression = it.cronExpression ?: "" } catch (Exception ignore) {}
            r
        }.sort { it.name ?: "" })
    } catch (Exception e) {
        ok([error: "Failed to list import configs: ${e.message}"])
    }
}

// ---- Object → Jira Tickets ----

def getObjectConnectedTickets(String objectId) {
    if (!objectId) return ok([error: "id parameter is required"])
    try {
        def objectFacade = getFacade("ObjectFacade")
        if (!objectFacade) return ok([error: "Assets not installed"])
        def tickets = []
        try {
            def ticketBeans = objectFacade.findTicketsByObjectId(objectId as int) ?: []
            tickets = ticketBeans.collect {
                [key: it.key ?: it.issueKey ?: "", summary: it.summary ?: ""]
            }
        } catch (Exception e1) {
            // Fallback: search Jira issues linked to this object via JQL
            try {
                def obj = objectFacade.loadObjectBean(objectId as int)
                if (obj) {
                    def jql = "\"object\" = ${obj.objectKey}"
                    def searchService = ComponentAccessor.getComponent(com.atlassian.jira.bc.issue.search.SearchService)
                    def user = ComponentAccessor.jiraAuthenticationContext.loggedInUser
                    def parseResult = searchService.parseQuery(user, jql)
                    if (parseResult.isValid()) {
                        def results = searchService.search(user, parseResult.query,
                            com.atlassian.jira.web.bean.PagerFilter.unlimitedFilter)
                        tickets = results.results?.take(50)?.collect { doc ->
                            def issue = ComponentAccessor.issueManager.getIssueObject(doc.id)
                            [key: issue?.key ?: "", summary: issue?.summary ?: "",
                             status: issue?.status?.name ?: "", type: issue?.issueType?.name ?: ""]
                        } ?: []
                    }
                }
            } catch (Exception e2) {
                return ok([error: "Could not find connected tickets: ${e1.message}"])
            }
        }
        ok([objectId: objectId, ticketCount: tickets.size(), tickets: tickets])
    } catch (Exception e) {
        ok([error: "Failed to get connected tickets: ${e.message}"])
    }
}

// --- Issue Worklogs ---

def getIssueWorklogs(String issueKey) {
    if (!issueKey) return ok([error: "key parameter is required"])
    def issueManager = ComponentAccessor.issueManager
    def issue = issueManager.getIssueByCurrentKey(issueKey)
    if (!issue) return notFound("Issue not found: ${issueKey}")

    def worklogManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.worklog.WorklogManager)
    def durationUtils = ComponentAccessor.getComponent(com.atlassian.jira.util.JiraDurationUtils)
    def worklogs = worklogManager.getByIssue(issue)

    long totalSeconds = 0
    def entries = worklogs.collect { wl ->
        totalSeconds += (wl.timeSpent ?: 0)
        def comment = wl.comment ?: ""
        if (comment.length() > 500) comment = comment.substring(0, 500) + "... [truncated]"
        [
            id              : wl.id,
            author          : [displayName: wl.authorObject?.displayName ?: "", key: wl.authorObject?.key ?: ""],
            timeSpentSeconds: wl.timeSpent,
            timeSpentDisplay: durationUtils.getShortFormattedDuration(wl.timeSpent),
            started         : wl.startDate?.format("yyyy-MM-dd'T'HH:mm:ss.SSSZ"),
            created         : wl.created?.format("yyyy-MM-dd'T'HH:mm:ss.SSSZ"),
            updated         : wl.updated?.format("yyyy-MM-dd'T'HH:mm:ss.SSSZ"),
            comment         : comment
        ]
    }

    ok([
        issueKey             : issueKey,
        count                : entries.size(),
        totalTimeSpentSeconds: totalSeconds,
        totalTimeSpentDisplay: durationUtils.getShortFormattedDuration(totalSeconds),
        worklogs             : entries
    ])
}

// ============================================================================
//  SCRIPTRUNNER CONFIGURATION — via SR REST API + OSGi services
// ============================================================================

// --------------- ScriptRunner Configuration via OSGi services ---------------
// Access SR config via its internal managers exposed as OSGi services.

def getSrOsgiService(Class clazz) {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        return sr?.getOsgiService(clazz)
    } catch (Exception ignored) {}
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        return sr?.getService(clazz)
    } catch (Exception ignored) {}
    try {
        return ComponentAccessor.getOSGiComponentInstanceOfType(clazz)
    } catch (Exception ignored) {}
    return null
}

// Safely extract properties from any object using reflection
def extractProps(obj) {
    if (obj == null) return null
    if (obj instanceof Map) return obj
    def map = [:]
    obj.class.methods.each { m ->
        def name = m.name
        if (m.parameterCount == 0 && !name.startsWith("wait") && name != "getClass" && name != "hashCode" && name != "toString" && name != "notify" && name != "notifyAll") {
            if (name.startsWith("get") && name.length() > 3) {
                try {
                    def key = name[3].toLowerCase() + name.substring(4)
                    def val = m.invoke(obj)
                    if (val != null) {
                        if (val instanceof String || val instanceof Number || val instanceof Boolean) {
                            map[key] = val
                        } else if (val instanceof Collection) {
                            map[key] = val.collect { it?.toString() }
                        } else if (val instanceof Map) {
                            map[key] = val
                        } else {
                            map[key] = val.toString()
                        }
                    }
                } catch (Exception ignored) {}
            } else if (name.startsWith("is") && name.length() > 2) {
                try {
                    def key = name[2].toLowerCase() + name.substring(3)
                    map[key] = m.invoke(obj)
                } catch (Exception ignored) {}
            }
        }
    }
    return map
}

// Helper: extract listener summary with scripts from extractProps result
def formatListener(props) {
    def params = props.params
    def result = [
        id      : params?.id ?: props.parentConfigurationId ?: "",
        name    : params?.name ?: params?.FIELD_LISTENER_NOTES ?: params?.FIELD_NOTES ?: "",
        events  : props.eventIds ?: [],
        projects: params?.projects ?: [],
        disabled: params?.disabled ?: false,
        cannedScript: props.scriptName ?: params?.get("canned-script") ?: ""
    ]
    // Extract inline script
    def sfos = params?.FIELD_SCRIPT_FILE_OR_SCRIPT
    if (sfos instanceof Map) {
        result.script = sfos.script ?: ""
        result.scriptFile = sfos.scriptFile ?: ""
    } else if (sfos instanceof String) {
        result.scriptFile = sfos
    }
    return result
}

def listSrListeners(String project) {
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.scriptrunner.runner.ListenerManager"))
        if (!mgr) return ok([error: "ListenerManager not available"])
        def listeners = mgr.getListeners()
        def results = listeners?.collect { formatListener(extractProps(it)) } ?: []
        // Filter by project if specified
        if (project) {
            def pUpper = project.toUpperCase()
            results = results.findAll { l ->
                l.projects?.any { it?.toString()?.toUpperCase()?.contains(pUpper) } ||
                l.name?.toString()?.toUpperCase()?.contains(pUpper)
            }
        }
        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read SR listeners", detail: e.message])
    }
}

def getSrListener(String id) {
    if (!id) return notFound("Listener ID required")
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.scriptrunner.runner.ListenerManager"))
        if (!mgr) return ok([error: "ListenerManager not available"])
        def listeners = mgr.getListeners()
        def target = listeners?.find { l ->
            def props = extractProps(l)
            def lid = props.params?.id ?: props.parentConfigurationId ?: ""
            lid.toString() == id
        }
        return target ? ok(formatListener(extractProps(target))) : notFound("Listener not found: ${id}")
    } catch (Exception e) {
        return ok([error: "Cannot read SR listener ${id}", detail: e.message])
    }
}

def listSrBehaviours(String project) {
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.jira.behaviours.BehaviourManager"))
        if (!mgr) return ok([error: "BehaviourManager not available"])

        // If project specified, filter by mappings (ProjectCoordinates/ServiceDeskCoordinates)
        if (project) {
            def pKey = project.toUpperCase()
            def allBM = mgr.getAllBehavioursAndMappings()
            def results = []
            def debugInfo = [total: allBM?.size(), matched: 0, errors: []]
            allBM?.each { item ->
                try {
                    def mappingsList = item.mappings
                    if (mappingsList == null || mappingsList.isEmpty()) return // skip unmapped
                    def isMapped = false
                    def parsedMappings = []
                    mappingsList.each { m ->
                        def clsName = m?.class?.name ?: ""
                        if (clsName.contains("ProjectCoordinates")) {
                            def projKey = m.project?.key?.toUpperCase() ?: ""
                            parsedMappings << [type: "project", project: m.project?.key, issueType: m.issuetype?.name]
                            if (projKey == pKey) isMapped = true
                        } else if (clsName.contains("ServiceDeskCoordinates")) {
                            def sdName = m.servicedesk?.name?.toUpperCase() ?: ""
                            parsedMappings << [type: "servicedesk", serviceDesk: m.servicedesk?.name, requestType: m.requesttype?.name]
                            if (sdName == pKey) isMapped = true
                            try {
                                if (m.servicedesk?.project?.key?.toUpperCase() == pKey) isMapped = true
                            } catch (Exception ignored) {}
                        }
                    }
                    if (isMapped) {
                        debugInfo.matched++
                        results << [
                            id           : item.id ?: "",
                            name         : item.name ?: "",
                            guideWorkflow: item.guideWorkflow ?: "",
                            disabled     : item.disabled ?: false,
                            fieldCount   : item.fields?.size() ?: 0,
                            mappings     : parsedMappings
                        ]
                    }
                } catch (Exception e) {
                    debugInfo.errors << "${item.name}: ${e.message}"
                }
            }
            // If debug needed, add: results << [_debug: debugInfo]
            return ok(results.isEmpty() ? [_debug: debugInfo] : results)
        }

        // No project filter — return all configs compact
        def configs = mgr.getAllConfigs()
        def results = []
        configs?.each { entry ->
            def beh = entry.value
            def name = ""
            def wf = ""
            try { name = beh?.name ?: "" } catch (Exception ignored) {}
            try { wf = beh?.guideWorkflow ?: "" } catch (Exception ignored) {}
            def disabled = false
            try { disabled = beh?.disabled ?: false } catch (Exception ignored) {}
            results << [
                id           : entry.key?.toString() ?: "",
                name         : name,
                guideWorkflow: wf,
                disabled     : disabled,
                fieldCount   : beh?.fields?.size() ?: 0
            ]
        }
        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read SR behaviours", detail: e.message])
    }
}

def getSrBehaviour(String id) {
    if (!id) return notFound("Behaviour ID required")
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.jira.behaviours.BehaviourManager"))
        if (!mgr) return ok([error: "BehaviourManager not available"])

        // Search in all configs
        def configs = mgr.getAllConfigs()
        def target = null
        configs?.each { entry ->
            if (entry.key?.toString() == id) target = entry
        }
        if (!target) return notFound("Behaviour not found: ${id}")

        def beh = target.value
        def result = [
            id         : id,
            name       : beh?.name ?: "",
            description: beh?.description ?: "",
            disabled   : beh?.disabled ?: false,
            guideWorkflow: beh?.guideWorkflow ?: ""
        ]

        // Extract fields with their scripts
        def fieldsList = []
        beh?.fields?.each { f ->
            def fieldMap = [:]
            try {
                // Basic field properties
                try { fieldMap.fieldId = f.id } catch (Exception ignored) {}
                try { fieldMap.type = f.class?.simpleName } catch (Exception ignored) {}
                try { fieldMap.name = f.name } catch (Exception ignored) {}
                try { fieldMap.readonly = f.readonly } catch (Exception ignored) {}
                try { fieldMap.hidden = f.hidden } catch (Exception ignored) {}
                try { fieldMap.required = f.required } catch (Exception ignored) {}
                try { fieldMap.uuid = f.uuid } catch (Exception ignored) {}

                // ServerValidationField contains ScriptConfiguration
                // The toString() of the field includes the ScriptConfiguration reference
                def fieldStr = f.toString()
                fieldMap.raw = fieldStr

                // Try to access the ScriptConfiguration through all possible paths
                def scriptConfig = null
                f.class.methods.each { m ->
                    if (m.parameterCount == 0 && !scriptConfig) {
                        def rtype = m.returnType?.name ?: ""
                        if (rtype.contains("ScriptConfiguration") || rtype.contains("Configuration")) {
                            try {
                                scriptConfig = m.invoke(f)
                            } catch (Exception ignored) {}
                        }
                    }
                }

                if (scriptConfig) {
                    try {
                        fieldMap.scriptFile = scriptConfig.scriptFile ?: ""
                    } catch (Exception ignored) {}
                    try {
                        fieldMap.inlineScript = scriptConfig.inlineScript ?: ""
                    } catch (Exception ignored) {}
                    try {
                        fieldMap.script = scriptConfig.script ?: ""
                    } catch (Exception ignored) {}
                    try {
                        scriptConfig.properties.findAll { k, v -> k != "class" && v != null }.each { k, v ->
                            if (!fieldMap.containsKey(k)) {
                                fieldMap["config_${k}"] = (v instanceof String || v instanceof Number || v instanceof Boolean) ? v : v.toString()
                            }
                        }
                    } catch (Exception ignored) {}
                }

                // Also check if the field has serverValidation with scripts
                // In SR 9.x, the actual scripts are in BehaviourEditState.fields[].ServerValidationField
                // which wraps a ScriptConfiguration
                // Try getting it from the original BehaviourEditState
                if (!fieldMap.containsKey("inlineScript") && !fieldMap.containsKey("scriptFile")) {
                    // Try to find the field config in the raw BehaviourEditState
                    def behStr = beh.toString()
                    def uuid = fieldMap.uuid ?: ""
                    if (uuid && behStr.contains(uuid)) {
                        // Extract the portion around this field's UUID
                        def idx = behStr.indexOf(uuid)
                        def start = Math.max(0, idx - 200)
                        def end = Math.min(behStr.length(), idx + 500)
                        fieldMap.context = behStr.substring(start, end)
                    }
                }

            } catch (Exception e) {
                fieldMap.error = e.message
            }
            fieldsList << fieldMap
        }
        result.fields = fieldsList

        // Init script
        try {
            if (beh?.init) result.initScript = beh.init.toString()
        } catch (Exception ignored) {}

        return ok(result)
    } catch (Exception e) {
        return ok([error: "Cannot read SR behaviour ${id}", detail: e.message])
    }
}

def listSrScriptFields(String project) {
    try {
        def cfm = ComponentAccessor.getCustomFieldManager()
        def srFields = cfm.getCustomFieldObjects().findAll { cf ->
            def typeKey = cf.getCustomFieldType()?.getKey() ?: ""
            typeKey.contains("scriptrunner") || typeKey.contains("com.onresolve")
        }
        def results = srFields.collect { cf ->
            def projectKeys = []
            try {
                cf.getConfigurationSchemes()?.each { scheme ->
                    scheme.getAssociatedProjectObjects()?.each { p -> projectKeys << p.key }
                }
            } catch (Exception ignored) {}
            [
                id         : cf.id,
                name       : cf.name,
                description: cf.description ?: "",
                typeKey    : cf.getCustomFieldType()?.getKey() ?: "",
                typeName   : cf.getCustomFieldType()?.getName() ?: "",
                projects   : projectKeys ?: ["global"]
            ]
        }
        if (project) {
            def pUpper = project.toUpperCase()
            results = results.findAll { f ->
                f.projects?.any { it?.toUpperCase() == pUpper } || f.projects?.contains("global")
            }
        }
        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read SR script fields", detail: e.message])
    }
}

def getSrScriptField(String id) {
    // Script field configs are stored in SR's internal AO/REST API.
    // The Python MCP server reads them directly via SR REST API.
    // This Groovy endpoint only provides basic custom field metadata as fallback.
    if (!id) return notFound("Script field ID required")
    try {
        def cf = ComponentAccessor.getCustomFieldManager().getCustomFieldObject(id)
        if (!cf) return notFound("Field not found: ${id}")
        return ok([
            id         : cf.id,
            name       : cf.name,
            description: cf.description ?: "",
            typeKey    : cf.getCustomFieldType()?.getKey() ?: "",
            typeName   : cf.getCustomFieldType()?.getName() ?: "",
            searcherKey: cf.getCustomFieldSearcher()?.getDescriptor()?.getCompleteKey() ?: "",
            hint       : "Full script config available via SR REST API /rest/scriptrunner/latest/scriptfields"
        ])
    } catch (Exception e) {
        return ok([error: "Cannot read SR script field ${id}", detail: e.message])
    }
}

def extractScriptFromConfig(obj) {
    if (obj == null) return null
    def str = obj.toString()
    // ScriptConfiguration objects have script/scriptFile in their params
    def result = [:]
    try {
        if (obj.hasProperty("script")) result.script = obj.script?.toString()
        if (obj.hasProperty("scriptFile")) result.scriptFile = obj.scriptFile?.toString()
        if (obj.hasProperty("inlineScript")) result.inlineScript = obj.inlineScript?.toString()
    } catch (Exception ignored) {}
    // Try params map
    try {
        def params = obj.hasProperty("params") ? obj.params : null
        if (params instanceof Map) {
            def sfos = params.FIELD_SCRIPT_FILE_OR_SCRIPT ?: params.scriptFileOrScript
            if (sfos instanceof Map) {
                if (sfos.script) result.script = sfos.script
                if (sfos.scriptFile) result.scriptFile = sfos.scriptFile
            }
            def notes = params.FIELD_NOTES ?: params.notes
            if (notes) result.notes = notes
        }
    } catch (Exception ignored) {}
    // Try reflection
    if (!result.script && !result.scriptFile) {
        try {
            obj.class.methods.findAll { m -> m.parameterCount == 0 && (m.name.contains("cript") || m.name.contains("file")) }.each { m ->
                try {
                    def val = m.invoke(obj)
                    if (val && val.toString().length() > 1) {
                        result[m.name] = val.toString().take(2000)
                    }
                } catch (Exception ignored) {}
            }
        } catch (Exception ignored) {}
    }
    return result.isEmpty() ? null : result
}

def listSrFragments() {
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.scriptrunner.fragments.IFragmentsManager"))
        if (!mgr) return ok([error: "FragmentsManager not available"])
        def fragments = mgr.getRegisteredFragments()
        return ok(fragments?.collect { frag ->
            def props = extractProps(frag)
            // Extract condition script if present
            if (props.condition && props.condition.toString().contains("ScriptConfiguration")) {
                try {
                    def condObj = frag.class.methods.find { it.name == "getCondition" && it.parameterCount == 0 }?.invoke(frag)
                    def condScript = extractScriptFromConfig(condObj)
                    if (condScript) props.conditionScript = condScript
                } catch (Exception ignored) {}
            }
            // Extract action script if present
            if (props.additionalScript && props.additionalScript.toString().contains("ScriptConfiguration")) {
                try {
                    def actObj = frag.class.methods.find { it.name == "getAdditionalScript" && it.parameterCount == 0 }?.invoke(frag)
                    def actScript = extractScriptFromConfig(actObj)
                    if (actScript) props.actionScript = actScript
                } catch (Exception ignored) {}
            }
            props
        } ?: [])
    } catch (Exception e) {
        return ok([error: "Cannot read SR fragments", detail: e.message])
    }
}

def listSrJobs(String project) {
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.scriptrunner.scheduled.ScheduledScriptJobManager"))
        if (!mgr) return ok([error: "ScheduledScriptJobManager not available"])
        def jobs = mgr.getCurrentlyScheduledJobs()
        def results = jobs?.collect { extractProps(it) } ?: []
        if (project) {
            def pUpper = project.toUpperCase()
            results = results.findAll { j ->
                j.notes?.toString()?.toUpperCase()?.contains(pUpper) ||
                j.jql?.toString()?.toUpperCase()?.contains(pUpper) ||
                j.toString()?.toUpperCase()?.contains(pUpper)
            }
        }
        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read SR jobs", detail: e.message])
    }
}

def listSrEndpoints() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def homeDir = sr?.getHomeScriptDir()
        def endpoints = []

        // Method 1: Scan all .groovy files for endpoint definitions (CustomEndpointDelegate)
        if (homeDir?.exists()) {
            homeDir.eachFileRecurse { file ->
                if (file.name.endsWith(".groovy")) {
                    try {
                        def content = file.text
                        if (content.contains("CustomEndpointDelegate") || content.contains("httpMethod")) {
                            // Extract endpoint names from closure definitions
                            def matcher = content =~ /(\w+)\s*\(\s*httpMethod\s*:\s*"(\w+)"/
                            def endpointDefs = []
                            while (matcher.find()) {
                                endpointDefs << [name: matcher.group(1), method: matcher.group(2)]
                            }
                            // Extract groups
                            def groupMatcher = content =~ /groups\s*:\s*\[([^\]]+)\]/
                            def groups = []
                            if (groupMatcher.find()) {
                                groups = groupMatcher.group(1).replaceAll('"', '').split(',').collect { it.trim() }
                            }
                            endpoints << [
                                file         : file.name,
                                path         : file.absolutePath,
                                size         : file.length(),
                                lastModified : new Date(file.lastModified()).format("yyyy-MM-dd HH:mm:ss"),
                                endpoints    : endpointDefs,
                                groups       : groups,
                                scriptPreview: content.take(500)
                            ]
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        // Method 2: Also check scripts/rest/ for REST endpoint scripts
        def restDir = homeDir ? new File(homeDir, "rest") : null
        if (restDir?.exists()) {
            restDir.eachFileRecurse { file ->
                if (file.name.endsWith(".groovy")) {
                    endpoints << [
                        file         : file.name,
                        path         : file.absolutePath,
                        type         : "rest-directory",
                        size         : file.length(),
                        lastModified : new Date(file.lastModified()).format("yyyy-MM-dd HH:mm:ss"),
                        scriptPreview: file.text.take(500)
                    ]
                }
            }
        }

        return ok(endpoints ?: [hint: "No endpoint scripts found in ${homeDir?.absolutePath ?: 'unknown'}"])
    } catch (Exception e) {
        return ok([error: "Cannot read SR endpoints", detail: e.message])
    }
}

def listSrEscalationServices(String project) {
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.scriptrunner.scheduled.ScheduledScriptJobManager"))
        if (!mgr) return ok([error: "ScheduledScriptJobManager not available"])
        def allJobs = mgr.getCurrentlyScheduledJobs()
        def escalations = allJobs?.findAll { job ->
            try {
                def props = extractProps(job)
                return props?.cannedScript?.toString()?.contains("EscalationService")
            } catch (Exception ignored) { return false }
        }
        def results = escalations?.collect { extractProps(it) } ?: []
        if (project) {
            def pUpper = project.toUpperCase()
            results = results.findAll { e ->
                e.notes?.toString()?.toUpperCase()?.contains(pUpper) ||
                e.jql?.toString()?.toUpperCase()?.contains(pUpper)
            }
        }
        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read SR escalation services", detail: e.message])
    }
}

def getSrEscalationService(String id) {
    if (!id) return notFound("Escalation service ID required")
    try {
        def mgr = getSrOsgiService(Class.forName("com.onresolve.scriptrunner.scheduled.ScheduledScriptJobManager"))
        if (!mgr) return ok([error: "ScheduledScriptJobManager not available"])
        def job = mgr.get(id)
        return job ? ok(extractProps(job)) : notFound("Escalation service not found: ${id}")
    } catch (Exception e) {
        return ok([error: "Cannot read SR escalation service ${id}", detail: e.message])
    }
}

// ============================================================================
//  JMWE (Jira Misc Workflow Extensions) — Event-Based Actions via AO
// ============================================================================

def getJmweAo() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def osgiCtx = sr.getOurBundle().bundleContext
        def jmweBundle = osgiCtx.bundles.find { it.symbolicName?.contains("jmwe") }
        if (!jmweBundle) return null
        def jmweCtx = jmweBundle.bundleContext
        def aoRef = jmweCtx.getServiceReference("com.atlassian.activeobjects.external.ActiveObjects")
        return aoRef ? jmweCtx.getService(aoRef) : null
    } catch (Exception ignored) {
        return null
    }
}

def getJmweClassLoader() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def osgiCtx = sr.getOurBundle().bundleContext
        def jmweBundle = osgiCtx.bundles.find { it.symbolicName?.contains("jmwe") }
        return jmweBundle?.adapt(org.osgi.framework.wiring.BundleWiring.class)?.classLoader
    } catch (Exception ignored) {
        return null
    }
}

def resolveProjectKeys(String projectIds) {
    if (!projectIds) return []
    def pm = ComponentAccessor.getProjectManager()
    return projectIds.split(",").collect { id ->
        try {
            def p = pm.getProjectObj(Long.parseLong(id.trim()))
            p ? p.key : id.trim()
        } catch (Exception ignored) { id.trim() }
    }
}

def resolveIssueTypeNames(String issueTypeIds) {
    if (!issueTypeIds) return []
    def itm = ComponentAccessor.getComponent(com.atlassian.jira.config.IssueTypeManager.class)
    return issueTypeIds.split(",").collect { id ->
        try {
            def it = itm.getIssueType(id.trim())
            it ? it.name : id.trim()
        } catch (Exception ignored) { id.trim() }
    }
}

def parseJmweEvent(String eventJson) {
    if (!eventJson) return [:]
    try {
        def parsed = new JsonSlurper().parseText(eventJson)
        def eventId = parsed.eventId
        // Map event IDs to names
        def eventNames = [
            1: "Issue Created", 2: "Issue Updated", 3: "Issue Assigned",
            4: "Issue Resolved", 5: "Issue Closed", 6: "Issue Commented",
            7: "Issue Reopened", 8: "Issue Deleted", 9: "Issue Moved",
            10: "Work Logged On Issue", 13: "Issue Comment Edited",
            14: "Issue Worklog Updated", 15: "Issue Worklog Deleted",
            16: "Generic Event", 17: "Issue Comment Deleted",
            (-1): "Any Issue Event", (-2): "Issue Field Value Changed"
        ]
        return [
            eventId  : eventId,
            eventName: eventNames[eventId] ?: "Event #${eventId}",
            fields   : parsed.fields ?: [],
            fromStatuses: parsed.fromStatuses ?: [],
            toStatuses  : parsed.toStatuses ?: []
        ]
    } catch (Exception ignored) {
        return [raw: eventJson]
    }
}

def formatJmweAction(entity, boolean detailed = false) {
    def event = parseJmweEvent(entity.getEvent())
    def result = [
        id            : entity.getID() ?: "",
        name          : entity.getName() ?: "",
        description   : entity.getDescription() ?: "",
        event         : event,
        projects      : resolveProjectKeys(entity.getProjects()),
        issueTypes    : resolveIssueTypeNames(entity.getIssueTypes()),
        enabled       : entity.getEnable(),
        jql           : entity.getJQL() ?: "",
        groovyExpression: entity.getGroovyExpression() ?: "",
        startDate     : entity.getStartDate() ?: "",
        endDate       : entity.getEndDate() ?: "",
        ignoreJMWEChanges: entity.getIgnoreJMWEChanges(),
        stopAtErrors  : entity.getStopAtErrors()
    ]

    // Only include post-functions in detailed view (get by id)
    if (detailed) {
        def postFunctions = []
        try {
            entity.getPostFunctions()?.each { pf ->
                def pfMap = [:]
                try { pfMap.id = pf.getID() } catch (Exception ignored) {}
                try { pfMap.name = pf.getName() } catch (Exception ignored) {}
                try { pfMap.description = pf.getDescription() } catch (Exception ignored) {}
                // Get all accessible string properties via reflection
                // Extract meaningful properties, skip AO internals
                def skipKeys = ["entityManager", "entityProxy", "action", "entityType", "tableName"] as Set
                pf.class.interfaces.each { iface ->
                    iface.methods.each { m ->
                        if (m.parameterCount == 0 && m.name.startsWith("get") && m.name != "getClass" && m.name != "getEntityType") {
                            try {
                                def key = m.name[3].toLowerCase() + m.name.substring(4)
                                if (key in skipKeys || pfMap.containsKey(key)) return
                                def val = m.invoke(pf)
                                if (val != null) {
                                    pfMap[key] = (val instanceof String || val instanceof Number || val instanceof Boolean) ? val : val.toString()
                                }
                            } catch (Exception ignored) {}
                        }
                    }
                }
                postFunctions << pfMap
            }
        } catch (Exception e) {
            result.postFunctionError = e.message
        }
        result.postFunctions = postFunctions
    } else {
        // Just count
        try {
            result.postFunctionCount = entity.getPostFunctions()?.length ?: 0
        } catch (Exception ignored) {
            result.postFunctionCount = 0
        }
    }

    return result
}

def listJmweEventActions(String project) {
    try {
        def ao = getJmweAo()
        if (!ao) return ok([error: "JMWE not available or AO not accessible"])
        def cl = getJmweClassLoader()
        if (!cl) return ok([error: "Cannot get JMWE classloader"])

        def toClass = cl.loadClass("com.innovalog.jmwe.actions.storage.EventBasedActionTO")
        def entities = ao.find(toClass)

        def results = entities?.collect { formatJmweAction(it, false) } ?: []

        // Filter by project if specified
        if (project) {
            def pUpper = project.toUpperCase()
            results = results.findAll { action ->
                action.projects?.any { it?.toUpperCase() == pUpper }
            }
        }

        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read JMWE event-based actions", detail: e.message])
    }
}

def getJmweEventAction(String id) {
    if (!id) return notFound("Action ID required")
    try {
        def ao = getJmweAo()
        if (!ao) return ok([error: "JMWE not available"])
        def cl = getJmweClassLoader()
        if (!cl) return ok([error: "Cannot get JMWE classloader"])

        def toClass = cl.loadClass("com.innovalog.jmwe.actions.storage.EventBasedActionTO")
        def entities = ao.find(toClass)
        def target = entities?.find { it.getID() == id }
        if (!target) return notFound("JMWE event action not found: ${id}")

        return ok(formatJmweAction(target, true))
    } catch (Exception e) {
        return ok([error: "Cannot read JMWE event action ${id}", detail: e.message])
    }
}

// --- JMWE Shared Actions -----------------------------------------------------
// JMWE stores Shared Actions (reusable post-functions/conditions/validators
// referenced from workflow transitions) in AO. Class naming varies across
// JMWE versions — try the known candidates in order.

def JMWE_SHARED_ACTION_CLASSES = [
    "com.innovalog.jmwe.actions.storage.SharedActionTO",
    "com.innovalog.jmwe.sharedactions.storage.SharedActionTO",
    "com.innovalog.jmwe.actions.shared.storage.SharedActionTO",
    "com.innovalog.jmwe.actions.storage.SharedPostFunctionTO",
    "com.innovalog.jmwe.actions.storage.SharedConditionTO",
    "com.innovalog.jmwe.actions.storage.SharedValidatorTO",
]

def loadJmweSharedActionClasses(classLoader) {
    def loaded = []
    JMWE_SHARED_ACTION_CLASSES.each { name ->
        try {
            loaded << classLoader.loadClass(name)
        } catch (ClassNotFoundException ignored) {
            // ok — version mismatch; try next candidate
        }
    }
    return loaded
}

// Extract all zero-arg getters as a property map. Used for Shared Actions where
// the schema varies by JMWE version and we don't want to hardcode field names.
def dumpGetters(entity) {
    if (entity == null) return [:]
    def skipKeys = ["entityManager", "entityProxy", "action", "entityType", "tableName", "class"] as Set
    def result = [:]
    entity.class.interfaces.each { iface ->
        iface.methods.each { m ->
            if (m.parameterCount != 0) return
            if (!m.name.startsWith("get") && !m.name.startsWith("is")) return
            if (m.name in ["getClass", "getEntityType"]) return
            def prefix = m.name.startsWith("get") ? 3 : 2
            def key = m.name[prefix].toLowerCase() + m.name.substring(prefix + 1)
            if (key in skipKeys || result.containsKey(key)) return
            try {
                def val = m.invoke(entity)
                if (val == null) { result[key] = null; return }
                result[key] = (val instanceof String || val instanceof Number || val instanceof Boolean) ? val : val.toString()
            } catch (Exception ignored) {}
        }
    }
    return result
}

def formatJmweSharedAction(entity, String classSimpleName, boolean detailed = false) {
    def base = dumpGetters(entity)
    def out = [
        id        : base.iD ?: base.id ?: "",
        name      : base.name ?: "",
        type      : deriveSharedActionType(classSimpleName, base),
        sourceClass: classSimpleName,
    ]
    if (detailed) {
        // In detailed view dump everything so admin can inspect config JSON / scripts.
        out.putAll(base.findAll { k, _v -> !(k in ["iD"]) })
    } else {
        // Short view: just the most useful identifying fields.
        out.description = base.description ?: ""
        out.enabled = base.enable != null ? base.enable : base.enabled
    }
    return out
}

def deriveSharedActionType(String classSimpleName, Map props) {
    def lower = (classSimpleName ?: "").toLowerCase()
    if (lower.contains("postfunction")) return "post-function"
    if (lower.contains("condition"))    return "condition"
    if (lower.contains("validator"))    return "validator"
    // Some versions have a single SharedActionTO with a `type` field
    return props.type ?: props.kind ?: "shared-action"
}

def listJmweSharedActions(String typeFilter) {
    try {
        def ao = getJmweAo()
        if (!ao) return ok([error: "JMWE not available or AO not accessible"])
        def cl = getJmweClassLoader()
        if (!cl) return ok([error: "Cannot get JMWE classloader"])

        def classes = loadJmweSharedActionClasses(cl)
        if (!classes) return ok([
            error: "No JMWE Shared Action AO class found",
            hint : "Tried: ${JMWE_SHARED_ACTION_CLASSES.join(', ')}. JMWE may not ship shared actions in this version."
        ])

        def all = []
        classes.each { toClass ->
            try {
                def entities = ao.find(toClass)
                entities?.each { e -> all << formatJmweSharedAction(e, toClass.simpleName, false) }
            } catch (Exception ignored) {
                // skip this candidate — wrong schema for version
            }
        }

        if (typeFilter) {
            def f = typeFilter.toLowerCase()
            all = all.findAll { (it.type ?: "").toString().toLowerCase().contains(f) }
        }
        return ok(all)
    } catch (Exception e) {
        return ok([error: "Cannot read JMWE shared actions", detail: e.message])
    }
}

def getJmweSharedAction(String id) {
    if (!id) return notFound("Action ID required")
    try {
        def ao = getJmweAo()
        if (!ao) return ok([error: "JMWE not available"])
        def cl = getJmweClassLoader()
        if (!cl) return ok([error: "Cannot get JMWE classloader"])

        def classes = loadJmweSharedActionClasses(cl)
        if (!classes) return ok([error: "No JMWE Shared Action AO class found"])

        for (toClass in classes) {
            try {
                def entities = ao.find(toClass)
                def target = entities?.find { String.valueOf(it.getID()) == id }
                if (target) return ok(formatJmweSharedAction(target, toClass.simpleName, true))
            } catch (Exception ignored) {
                // continue
            }
        }
        return notFound("JMWE shared action not found: ${id}")
    } catch (Exception e) {
        return ok([error: "Cannot read JMWE shared action ${id}", detail: e.message])
    }
}

// ============================================================================
//  Structure Plugin — via OSGi StructureManager API
// ============================================================================

def getStructureManager() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def ctx = sr.getOurBundle().bundleContext
        def ref = ctx.getServiceReference("com.almworks.jira.structure.api.structure.StructureManager")
        return ref ? ctx.getService(ref) : null
    } catch (Exception ignored) {
        return null
    }
}

def getStructureViewLevel() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def ctx = sr.getOurBundle().bundleContext
        def structBundle = ctx.bundles.find { it.symbolicName?.contains("structure") }
        def cl = structBundle.adapt(org.osgi.framework.wiring.BundleWiring.class)?.classLoader
        def permClass = cl.loadClass("com.almworks.jira.structure.api.permissions.PermissionLevel")
        return permClass.getField("VIEW").get(null)
    } catch (Exception ignored) {
        return null
    }
}

def getStructureGeneratorManager() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def ctx = sr.getOurBundle().bundleContext
        def ref = ctx.getServiceReference("com.almworks.jira.structure.api.generator.GeneratorManager")
        return ref ? ctx.getService(ref) : null
    } catch (Exception ignored) {
        return null
    }
}

def getStructureForestService() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def ctx = sr.getOurBundle().bundleContext
        def ref = ctx.getServiceReference("com.almworks.jira.structure.api.forest.ForestService")
        return ref ? ctx.getService(ref) : null
    } catch (Exception ignored) {
        return null
    }
}

def formatStructure(s) {
    def result = [
        id         : s.getId(),
        name       : s.getName(),
        description: s.getDescription() ?: ""
    ]
    try { result.archived = s.isArchived() } catch (Exception ignored) {}
    try {
        def owner = s.getOwner()
        result.owner = owner?.username ?: owner?.key ?: ""
    } catch (Exception ignored) {}
    return result
}

def listStructures(String search) {
    try {
        def mgr = getStructureManager()
        if (!mgr) return ok([error: "Structure plugin not available"])
        def viewLevel = getStructureViewLevel()
        if (!viewLevel) return ok([error: "Cannot resolve VIEW permission level"])

        def structures = mgr.getAllStructures(viewLevel, true) // include archived
        def results = structures?.collect { formatStructure(it) } ?: []

        if (search) {
            def searchUpper = search.toUpperCase()
            results = results.findAll { s ->
                s.name?.toUpperCase()?.contains(searchUpper) ||
                s.description?.toUpperCase()?.contains(searchUpper)
            }
        }

        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot read structures", detail: e.message])
    }
}

def getStructure(String id) {
    if (!id) return notFound("Structure ID required")
    try {
        def mgr = getStructureManager()
        if (!mgr) return ok([error: "Structure plugin not available"])
        def viewLevel = getStructureViewLevel()

        def structure = mgr.getStructure(Long.parseLong(id), viewLevel)
        if (!structure) return notFound("Structure not found: ${id}")

        def result = formatStructure(structure)

        // Get generators (automations) for this structure
        try {
            def genMgr = getStructureGeneratorManager()
            if (genMgr) {
                // Generators are linked to structures via their structureId param
                def gen = genMgr.getGenerator(Long.parseLong(id))
                if (gen) {
                    result.generator = [
                        id    : gen.getId(),
                        type  : gen.getGeneratorType(),
                        params: gen.getParams()
                    ]
                }
            }
        } catch (Exception ignored) {}

        // Get forest (tree) summary - row count
        try {
            def forestSvc = getStructureForestService()
            if (forestSvc) {
                def forest = forestSvc.getForest(Long.parseLong(id))
                if (forest) {
                    result.rowCount = forest.size()
                }
            }
        } catch (Exception ignored) {}

        // Find all views associated with this structure (reverse lookup)
        try {
            def viewMgr = getStructureViewManager()
            if (viewMgr) {
                def structId = Long.parseLong(id)
                def associatedViews = []
                // Use getViewsForStructure if available
                try {
                    def views = viewMgr.getViewsForStructure(structId, viewLevel)
                    views?.each { v ->
                        associatedViews << [id: v.getId(), name: v.getName(), columnCount: v.getSpecification()?.getColumns()?.size() ?: 0]
                    }
                } catch (Exception ignored2) {
                    // Fallback: scan all views
                    def allViews = viewMgr.getViews(viewLevel)
                    allViews?.each { v ->
                        try {
                            def assocStr = viewMgr.getAssociatedStructures(v.getId())?.toString() ?: ""
                            if (assocStr.contains("[${structId}]") || assocStr.contains("${structure.getName()}[${structId}]")) {
                                associatedViews << [id: v.getId(), name: v.getName(), columnCount: v.getSpecification()?.getColumns()?.size() ?: 0]
                            }
                        } catch (Exception ignored3) {}
                    }
                }
                result.views = associatedViews
            }
        } catch (Exception e) {
            result.viewsError = e.message
        }

        return ok(result)
    } catch (Exception e) {
        return ok([error: "Cannot read structure ${id}", detail: e.message])
    }
}

def getStructureViewManager() {
    try {
        def sr = com.onresolve.scriptrunner.runner.ScriptRunnerImpl.scriptRunner
        def ctx = sr.getOurBundle().bundleContext
        def ref = ctx.getServiceReference("com.almworks.jira.structure.api.view.StructureViewManager")
        return ref ? ctx.getService(ref) : null
    } catch (Exception ignored) { return null }
}

def formatColumn(col) {
    def result = [key: col.getKey(), csid: col.getCsid()]
    try { result.name = col.getName() } catch (Exception ignored) {}
    try {
        def params = col.getParameters()
        if (params) {
            result.parameters = [:]
            params.each { k, v ->
                result.parameters[k] = (v instanceof Map) ? v : v?.toString()
            }
        }
    } catch (Exception ignored) {}
    // Resolve field names for field-type columns
    if (result.key == "field" && result.parameters?.field) {
        try {
            def fieldId = result.parameters.field
            def cfm = ComponentAccessor.getCustomFieldManager()
            def cf = cfm.getCustomFieldObject(fieldId)
            if (cf) result.fieldName = cf.name
            else {
                // System field
                def fm = ComponentAccessor.getFieldManager()
                def f = fm.getField(fieldId)
                if (f) result.fieldName = f.name
            }
        } catch (Exception ignored) {}
    }
    return result
}

def listStructureViews(String search) {
    try {
        def viewMgr = getStructureViewManager()
        if (!viewMgr) return ok([error: "Structure ViewManager not available"])
        def viewLevel = getStructureViewLevel()

        def views = viewMgr.getViews(viewLevel)
        def results = views?.collect { v ->
            def map = [id: v.getId(), name: v.getName(), description: v.getDescription() ?: ""]
            try { map.owner = v.getOwner()?.username ?: "" } catch (Exception ignored) {}
            try { map.shared = v.isShared() } catch (Exception ignored) {}
            try { map.public_ = v.isPublic() } catch (Exception ignored) {}
            try {
                def spec = v.getSpecification()
                map.columnCount = spec?.getColumns()?.size() ?: 0
            } catch (Exception ignored) {}
            map
        } ?: []

        if (search) {
            def sUp = search.toUpperCase()
            results = results.findAll { v -> v.name?.toUpperCase()?.contains(sUp) }
        }
        return ok(results)
    } catch (Exception e) {
        return ok([error: "Cannot list structure views", detail: e.message])
    }
}

def getStructureView(String id) {
    if (!id) return notFound("View ID required")
    try {
        def viewMgr = getStructureViewManager()
        if (!viewMgr) return ok([error: "Structure ViewManager not available"])
        def viewLevel = getStructureViewLevel()

        def view = viewMgr.getView(Long.parseLong(id), viewLevel)
        if (!view) return notFound("View not found: ${id}")

        def result = [
            id         : view.getId(),
            name       : view.getName(),
            description: view.getDescription() ?: ""
        ]
        try { result.owner = view.getOwner()?.username ?: "" } catch (Exception ignored) {}
        try { result.shared = view.isShared() } catch (Exception ignored) {}

        // Get columns with full details
        try {
            def spec = view.getSpecification()
            if (spec) {
                result.columns = spec.getColumns()?.collect { formatColumn(it) } ?: []
                result.columnDisplayMode = spec.getColumnDisplayMode()
                result.rowDisplayMode = spec.getRowDisplayMode()
                try { result.pins = spec.getPins()?.collect { it.toString() } ?: [] } catch (Exception ignored) {}
            }
        } catch (Exception e) {
            result.specError = e.message
        }

        // Associated structures
        try {
            def assoc = viewMgr.getAssociatedStructures(view.getId())
            result.associatedStructures = assoc?.collect { it?.toString() } ?: []
        } catch (Exception ignored) {}

        return ok(result)
    } catch (Exception e) {
        return ok([error: "Cannot read structure view ${id}", detail: e.message])
    }
}

// Audit log is accessed via REST API /rest/auditing/1.0/events from Python side

// ============================================================================
//  System Log — read from atlassian-jira.log file
// ============================================================================

def getSystemLog(String lines, String search) {
    try {
        def jiraHome = System.getProperty("jira.home") ?: "/var/atlassian/application-data/jira"
        def logFile = new File(jiraHome, "log/atlassian-jira.log")
        if (!logFile.exists()) return ok([error: "Log file not found", path: logFile.absolutePath])

        int maxLines = 100
        try { if (lines) maxLines = Integer.parseInt(lines.trim()) } catch (NumberFormatException ignored) { }
        maxLines = Math.max(1, Math.min(maxLines, 500))

        // Read backwards in chunks: cost depends on what we return, not on file
        // size. A search filter scans deeper (up to 50 MB) for matching lines.
        String needle = search ? search.toUpperCase() : null
        long maxScanBytes = needle ? 50L * 1024 * 1024 : 8L * 1024 * 1024
        int chunkSize = 64 * 1024
        List<String> newestFirst = []
        long scanned = 0
        byte[] carry = new byte[0]   // partial line that continues into the chunk read before
        def raf = new RandomAccessFile(logFile, "r")
        try {
            long pos = raf.length()
            while (pos > 0 && newestFirst.size() < maxLines && scanned < maxScanBytes) {
                int len = (int) Math.min((long) chunkSize, pos)
                pos -= len
                byte[] buf = new byte[len + carry.length]
                raf.seek(pos)
                raf.readFully(buf, 0, len)
                System.arraycopy(carry, 0, buf, len, carry.length)
                scanned += len

                int start = 0
                if (pos > 0) {
                    int nl = -1
                    for (int i = 0; i < buf.length; i++) { if (buf[i] == (byte) 10) { nl = i; break } }
                    if (nl < 0) { carry = buf; continue }
                    carry = Arrays.copyOfRange(buf, 0, nl)
                    start = nl + 1
                } else {
                    carry = new byte[0]
                }
                String[] chunkLines = new String(buf, start, buf.length - start, "UTF-8").split("\\r?\\n")
                for (int i = chunkLines.length - 1; i >= 0 && newestFirst.size() < maxLines; i--) {
                    String line = chunkLines[i]
                    if (!line) continue
                    if (needle == null || line.toUpperCase().contains(needle)) newestFirst << line
                }
            }
        } finally {
            raf.close()
        }

        return ok([
            file            : logFile.absolutePath,
            fileSizeMB      : (logFile.length() / 1024.0 / 1024.0).round(1),
            search          : search ?: null,
            scannedBytes    : scanned,
            scanLimitReached: scanned >= maxScanBytes && newestFirst.size() < maxLines,
            returned        : newestFirst.size(),
            lines           : newestFirst.reverse()
        ])
    } catch (Exception e) {
        return ok([error: "Cannot read system log", detail: e.message])
    }
}

// ============================================================================
//  RESPONSE HELPERS
// ============================================================================

def ok(data) {
    Response.ok(new JsonBuilder(data).toPrettyString()).header("Content-Type", "application/json").build()
}

def badRequest(data) {
    Response.status(400).entity(new JsonBuilder(data).toPrettyString()).header("Content-Type", "application/json").build()
}

def notFound(String msg) {
    Response.status(404).entity(new JsonBuilder([error: msg]).toString()).header("Content-Type", "application/json").build()
}
