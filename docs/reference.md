# Reference

Everything `AnyDI` exports, with the docstrings from the source.

## Container

::: anydi.Container

::: anydi.import_container

## Markers

`Provide` annotates a parameter with the type to resolve. `Inject` is the
default marker for a parameter that carries its type in the annotation.

::: anydi.Provide

::: anydi.Inject

## Scope decorators

Each of these marks a class as provided in one scope, so
[auto-registration](usage/providers/auto-registration.md) can pick it up
without a provider function.

::: anydi.singleton

::: anydi.transient

::: anydi.request

::: anydi.provided

## Providers and modules

::: anydi.provider

::: anydi.Provider

::: anydi.Module

::: anydi.injectable

## The global container

One container the whole application reaches by import, covered in
[Global Container](usage/global-container.md).

::: anydi.create_global_container

::: anydi.set_global_container

::: anydi.get_global_container

::: anydi.get_global_container_or_none

::: anydi.reset_global_container

::: anydi.global_ref

## Types

::: anydi.Scope
