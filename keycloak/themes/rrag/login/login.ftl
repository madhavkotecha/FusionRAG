<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
    <#if section = "header">
    <#elseif section = "form">
        <!-- Left panel: hero + particles -->
        <div class="rrag-hero">
            <canvas id="rrag-particles"></canvas>
            <div class="rrag-hero-content">
                <div class="rrag-brand">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                    </svg>
                </div>
                <h1>RRAG Platform</h1>
                <p class="tagline">RAG Research & Experimentation Platform</p>
                <div class="rrag-divider"></div>
                <ul class="rrag-features">
                    <li>
                        <div class="rrag-feature-icon">&#9889;</div>
                        <div class="rrag-feature-text">
                            <strong>Build Pipelines</strong>
                            <span>Design and test ingestion pipelines visually</span>
                        </div>
                    </li>
                    <li>
                        <div class="rrag-feature-icon">&#128269;</div>
                        <div class="rrag-feature-text">
                            <strong>Query &amp; Retrieve</strong>
                            <span>Multi-strategy retrieval across vector, graph &amp; keyword</span>
                        </div>
                    </li>
                    <li>
                        <div class="rrag-feature-icon">&#128202;</div>
                        <div class="rrag-feature-text">
                            <strong>Evaluate &amp; Iterate</strong>
                            <span>Track performance and refine your RAG system</span>
                        </div>
                    </li>
                </ul>
            </div>
        </div>

        <!-- Right panel: login form -->
        <div class="rrag-form-panel">
            <div class="rrag-mobile-brand">
                <div class="rrag-brand">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                    </svg>
                </div>
                <h1>RRAG Platform</h1>
            </div>
            <div class="rrag-form-wrapper">
                <p class="rrag-form-heading">Sign in to continue</p>

                <#if messagesPerField.existsError('username','password')>
                    <div class="alert alert-error">
                        ${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}
                    </div>
                </#if>

                <#if message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                    <div class="alert alert-${message.type}">
                        ${kcSanitize(message.summary)?no_esc}
                    </div>
                </#if>

                <form id="kc-form-login" onsubmit="login.disabled = true; return true;"
                      action="${url.loginAction}" method="post">

                    <label for="username">
                        <#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if>
                    </label>
                    <input tabindex="1" id="username" name="username" type="text"
                           autofocus autocomplete="username"
                           value="${(login.username!'')}"
                           placeholder="you@example.com" />

                    <label for="password">${msg("password")}</label>
                    <input tabindex="2" id="password" name="password" type="password"
                           autocomplete="current-password" placeholder="Enter your password" />

                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:1.25rem;">
                        <#if realm.rememberMe && !usernameEditDisabled??>
                            <div class="checkbox">
                                <label>
                                    <#if login.rememberMe??>
                                        <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" checked> ${msg("rememberMe")}
                                    <#else>
                                        <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox"> ${msg("rememberMe")}
                                    </#if>
                                </label>
                            </div>
                        </#if>
                        <#if realm.resetPasswordAllowed>
                            <a tabindex="5" href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a>
                        </#if>
                    </div>

                    <input tabindex="4" type="submit" name="login" id="kc-login" value="${msg("doLogIn")}" />
                </form>
            </div>
            <div class="rrag-footer">Powered by Keycloak</div>
        </div>
    </#if>
</@layout.registrationLayout>
